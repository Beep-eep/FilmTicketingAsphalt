from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from myapi.models import Order, SeatStatus, TicketService
from myapi.services import booking
from myapi.tests.helpers import client_for, make_cinema, make_user, seat_ids


@override_settings(STRIPE_SECRET_KEY="", PAYMENT_PROVIDER="demo")
class BookingFlowTests(TestCase):
    def setUp(self):
        self.film, self.room, self.show = make_cinema()
        self.alice = make_user()
        self.bob = make_user("bob", "bob@example.com")
        self.a = client_for(self.alice)
        self.b = client_for(self.bob)

    def book(self, client, numbers):
        return client.post("/api/orders/", {"showtime": self.show.ID, "seats": seat_ids(self.show, numbers)},
                           format="json", HTTP_ORIGIN="http://localhost:5173")

    def test_seat_map_reflects_holds(self):
        self.book(self.a, [1, 2])
        seats = {s["number"]: s for s in self.a.get(f"/api/showtimes/{self.show.ID}/").data["seats"]}
        self.assertEqual(seats[1]["status"], "held")
        self.assertEqual(seats[1]["label"], "A1")
        self.assertEqual(seats[20]["label"], "D5")
        self.assertTrue(seats[20]["premium"])
        self.assertEqual(seats[20]["price"], "13.00")
        public = {s["number"]: s for s in APIClient().get(f"/api/showtimes/{self.show.ID}/").data["seats"]}
        self.assertEqual(public[1]["status"], "taken")

    def test_order_totals_include_premium_seats(self):
        response = self.book(self.a, [1, 16])  # 16 is in premium row 4
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(response.data["amount_total"]), Decimal("23.00"))
        self.assertEqual(sorted(t["seat_label"] for t in response.data["tickets"]), ["A1", "D1"])

    def test_two_people_cannot_hold_the_same_seat(self):
        self.assertEqual(self.book(self.a, [3]).status_code, 201)
        response = self.book(self.b, [3, 4])
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "seats_taken")
        self.assertEqual(response.data["seats"], ["A3"])
        self.assertFalse(SeatStatus.objects.get(timeslot=self.show, seat_number=4).is_occupied)

    def test_choosing_again_replaces_the_previous_hold(self):
        self.book(self.a, [1, 2])
        self.book(self.a, [5])
        self.assertEqual(Order.objects.filter(user=self.alice, status="pending").count(), 1)
        self.assertFalse(SeatStatus.objects.get(timeslot=self.show, seat_number=1).is_occupied)

    def test_expired_hold_frees_seats(self):
        order_code = self.book(self.a, [7]).data["code"]
        Order.objects.filter(code=order_code).update(hold_expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.book(self.b, [7]).status_code, 201)
        self.assertEqual(Order.objects.get(code=order_code).status, "expired")

    def test_max_seats_and_closed_booking(self):
        with self.settings(MAX_SEATS_PER_ORDER=2):
            self.assertEqual(self.book(self.a, [1, 2, 3]).data["code"], "too_many_seats")
        self.show.begin_time = timezone.now() - timedelta(minutes=5)
        self.show.save()
        self.assertEqual(self.book(self.a, [1]).data["code"], "booking_closed")

    def test_demo_payment_then_refund_one_ticket(self):
        code = self.book(self.a, [1, 2]).data["code"]
        checkout = self.a.post(f"/api/orders/{code}/checkout/", {}, format="json",
                               HTTP_ORIGIN="http://localhost:5173")
        self.assertEqual(checkout.data["checkout_url"], f"http://localhost:5173/checkout/demo/{code}")
        declined = self.a.post(f"/api/payments/demo/{code}/", {"outcome": "decline"}, format="json")
        self.assertEqual(declined.status_code, 402)
        with self.captureOnCommitCallbacks(execute=True):
            paid = self.a.post(f"/api/payments/demo/{code}/", {"outcome": "success"}, format="json")
        self.assertEqual(paid.data["status"], "paid")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("A1, A2", mail.outbox[0].body)

        ticket_id = next(t["id"] for t in paid.data["tickets"] if t["seat_label"] == "A2")
        with self.captureOnCommitCallbacks(execute=True):
            refund = self.a.post(f"/api/orders/{code}/refund/", {"ticket_ids": [ticket_id]}, format="json")
        self.assertEqual(refund.data["refunded"], "10.00")
        self.assertEqual(refund.data["order"]["status"], "partially_refunded")
        self.assertFalse(SeatStatus.objects.get(timeslot=self.show, seat_number=2).is_occupied)
        self.assertTrue(SeatStatus.objects.get(timeslot=self.show, seat_number=1).is_occupied)
        self.assertEqual(len(mail.outbox), 2)

    def test_refunds_close_before_the_show(self):
        code = self.book(self.a, [1]).data["code"]
        self.a.post(f"/api/payments/demo/{code}/", {"outcome": "success"}, format="json")
        self.show.begin_time = timezone.now() + timedelta(minutes=30)
        self.show.save()
        response = self.a.post(f"/api/orders/{code}/refund/", {}, format="json")
        self.assertEqual(response.data["code"], "refund_closed")
        order = Order.objects.get(code=code)
        booking.refund_tickets(order, by_staff=True)  # staff can still refund from the admin
        self.assertEqual(Order.objects.get(code=code).status, "refunded")

    def test_people_cannot_touch_other_peoples_orders(self):
        code = self.book(self.a, [1]).data["code"]
        self.assertEqual(self.b.get(f"/api/orders/{code}/").status_code, 404)
        self.assertEqual(self.b.post(f"/api/orders/{code}/cancel/").status_code, 404)
        self.assertEqual(self.b.post(f"/api/payments/demo/{code}/", {}, format="json").status_code, 404)

    def test_cancel_pending_order(self):
        code = self.book(self.a, [9]).data["code"]
        response = self.a.post(f"/api/orders/{code}/cancel/")
        self.assertEqual(response.data["status"], "cancelled")
        self.assertFalse(SeatStatus.objects.get(timeslot=self.show, seat_number=9).is_occupied)
        self.assertEqual(TicketService.objects.get(order__code=code).status, "cancelled")

    def test_late_payment_after_seats_were_resold_is_reported_as_conflict(self):
        code = self.book(self.a, [11]).data["code"]
        Order.objects.filter(code=code).update(hold_expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.book(self.b, [11]).status_code, 201)
        order = Order.objects.get(code=code)
        self.assertEqual(booking.mark_order_paid(order), booking.PAID_CONFLICT)

    def test_showtime_creates_its_seats(self):
        self.assertEqual(self.show.seats.count(), 20)


class CatalogTests(TestCase):
    def setUp(self):
        self.film, self.room, self.show = make_cinema()
        self.film.actors.create(name="Famous Person")
        self.film.title_zh = "测试电影"
        self.film.save()

    def test_search_by_title_chinese_title_and_cast(self):
        for q in ("test fi", "测试", "famous"):
            data = APIClient().get("/api/films/", {"search": q}).data
            self.assertEqual([f["title"] for f in data], ["Test Film"], q)
        self.assertEqual(APIClient().get("/api/films/", {"search": "zzz"}).data, [])

    def test_film_detail_lists_cast_and_showtimes(self):
        detail = APIClient().get(f"/api/films/{self.film.ID}/").data
        self.assertEqual(detail["cast"], ["Famous Person"])
        self.assertEqual(len(detail["show_dates"]), 1)
        showtimes = APIClient().get(f"/api/films/{self.film.ID}/showtimes/").data
        self.assertEqual(showtimes[0]["seats_available"], 20)

    def test_reviews_create_then_update(self):
        user = make_user()
        c = client_for(user)
        self.assertEqual(c.post(f"/api/films/{self.film.ID}/reviews/", {"score": 8, "comment": "Great"},
                                format="json").status_code, 201)
        self.assertEqual(c.post(f"/api/films/{self.film.ID}/reviews/", {"score": 9}, format="json").status_code, 200)
        self.assertEqual(c.post(f"/api/films/{self.film.ID}/reviews/", {"score": 11}, format="json").status_code, 400)
        data = APIClient().get("/api/films/").data[0]
        self.assertEqual((data["avg_rating"], data["rating_count"]), (9.0, 1))
        self.assertEqual(APIClient().post(f"/api/films/{self.film.ID}/reviews/", {"score": 5}).status_code, 401)
