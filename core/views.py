from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, ListView, View
from django.shortcuts import redirect
from django.utils import timezone
from django.contrib import messages
from .models import Item, OrderItem, Order, Address, Payment, Coupon, Refund
from .forms import CheckoutForm, CouponForm, RefundForm

import random
import string
import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


def create_ref_code():
    return "".join(random.choices(string.ascii_letters + string.digits, k=20))


class HomeView(ListView):
    model = Item
    paginate_by = 10
    template_name = "home-page.html"


class OrderSummaryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):

        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                "object": order
            }
            return render(self.request, "order-summary.html", context)
        except ObjectDoesNotExist:
            messages.error(self.request, "You do not have an active Cart")
            return redirect("/")


def is_valid_form(values):
    valid = True
    for field in values:
        if field == "":
            valid = False
    return valid


class CheckoutView(View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            form = CheckoutForm()
            context = {
                "form": form,
                "CouponForm": CouponForm(),
                "order": order,
                "DISPLAY_COUPON_FORM": True
            }

            shipping_address_qs = Address.objects.filter(
                user=self.request.user, address_type="S", default=True)
            if shipping_address_qs.exists():
                context.update(
                    {"default_shipping_address": shipping_address_qs[0]})

            billing_address_qs = Address.objects.filter(
                user=self.request.user, address_type="B", default=True)
            if billing_address_qs.exists():
                context.update(
                    {"default_billing_address": billing_address_qs[0]})

            return render(self.request, "checkout-page.html", context)
        except ObjectDoesNotExist:
            messages.info(self.request, "You do not have an active order")
            return redirect("core:item_list")

    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST or None)
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            if form.is_valid():
                use_default_shipping = form.cleaned_data.get(
                    "use_default_shipping")
                if use_default_shipping:
                    address_qs = Address.objects.filter(
                        user=self.request.user, address_type="S", default=True)
                    if address_qs.exists():
                        shipping_address = address_qs[0]
                    else:
                        messages.info(
                            self.request, "You do not have a default shipping address")
                        return redirect("core:checkout")
                else:
                    shipping_address1 = form.cleaned_data.get(
                        'shipping_address')
                    shipping_address2 = form.cleaned_data.get(
                        'shipping_address2')
                    shipping_country = form.cleaned_data.get(
                        'shipping_country')
                    shipping_zip = form.cleaned_data.get('shipping_zip')

                    valid = is_valid_form(
                        [shipping_address1, shipping_country, shipping_zip])
                    if valid:
                        shipping_address = Address(
                            user=self.request.user,
                            street_address=shipping_address1,
                            apartment_address=shipping_address2,
                            country=shipping_country,
                            zip=shipping_zip,
                            address_type="S"
                        )
                        shipping_address.save()

                        set_default_shipping = form.cleaned_data.get(
                            'set_default_shipping')
                        if set_default_shipping:
                            shipping_address.default = True
                            shipping_address.save()

                    else:
                        message.info(
                            self.request, "Shipping Address form is not valid")
                        return redirect("core:checkout")

                order.shipping_address = shipping_address
                order.save()

                same_billing_address = form.cleaned_data.get(
                    "same_billing_address")
                use_default_billing = form.cleaned_data.get(
                    "use_default_billing")

                if same_billing_address:
                    billing_address = shipping_address
                    billing_address.pk = None
                    billing_address.save()
                    billing_address.address_type = "B"
                    billing_address.save()

                elif use_default_billing:
                    address_qs = Address.objects.filter(
                        user=self.request.user, address_type="B", default=True)
                    if address_qs.exists():
                        billing_address = address_qs[0]
                    else:
                        messages.info(
                            self.request, "You do not have a default billing address")
                        return redirect("core:checkout")
                else:
                    billing_address1 = form.cleaned_data.get(
                        'billing_address1')
                    billing_address2 = form.cleaned_data.get(
                        'billing_address2')
                    billing_country = form.cleaned_data.get(
                        'billing_country')
                    billing_zip = form.cleaned_data.get('billing_zip')

                    valid = is_valid_form(
                        [billing_address1, billing_country, billing_zip])
                    if valid:
                        billing_address = Address(
                            user=self.request.user,
                            street_address=billing_address1,
                            apartment_address=billing_address2,
                            country=billing_country,
                            zip=billing_zip,
                            address_type="B"
                        )
                        billing_address.save()

                        set_default_billing = form.cleaned_data.get(
                            'set_default_billing')
                        if set_default_billing:
                            billing_address.default = True
                            billing_address.save()

                    else:
                        message.info(
                            self.request, "Billing Address form is not valid")
                        return redirect("core:checkout")

                order.billing_address = billing_address
                order.save()

                same_billing_address = form.cleaned_data.get(
                    'same_billing_address')
                save_info = form.cleaned_data.get('save_info')
                payment_method = form.cleaned_data.get('payment_method')

                if payment_method == "S":
                    return redirect("core:payment", payment_method="stripe")
                elif payment_method == "P":
                    return redirect("core:payment", payment_method="paypal")
                else:
                    messages.warning(
                        self.request, "Invalid payment method selected")
                    return redirect("core:checkout")
        except ObjectDoesNotExist:
            messages.error(self.request, "You do not have an active Cart")
            return redirect("core:order-summary")

        context = {
            "form": form
        }
        return render(self.request, "checkout-page.html", context)


class PaymentView(View):
    def get(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        if order.billing_address:
            context = {
                "order": order,
                "DISPLAY_COUPON_FORM": False
            }
            return render(self.request, "payment.html", context)
        else:
            messages.warning(self.request, "You do not have a billing address")
            return redirect("core:checkout")

    def post(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        token = self.request.POST.get("stripeToken")

        try:
            charge = stripe.Charge.create(
                amount=int(order.get_total() * 100),  # convert to cents
                currency="usd",
                source=token
            )

            payment = Payment()
            payment.stripe_charge_id = charge["id"]
            payment.user = self.request.user
            payment.amount = order.get_total()
            payment.save()

            order_items = Order.items.all()
            order_items.update(ordered=True)
            for item in order_items:
                item.save()

            order.ordered = True
            order.payment = payment
            order.ref_code = create_ref_code()
            order.save()

            messages.success(self.request, "Your order was successful")
            return redirect("/")

        except stripe.error.CardError as e:
            body = e.json_body
            err = body.get("error", {})
            messages.error(self.request, f"{err.get('message')}")
            return redirect("/")

        except stripe.error.RateLimitError as e:
            messages.error(self.request, "Rate Limit Error, try again later")
            return redirect("/")

        except stripe.error.InvalidRequestError as e:
            messages.error(self.request, "Invalid Request Error")
            return redirect("/")

        except stripe.error.AuthenticationError as e:
            messages.error(self.request, "Authentication Error")
            return redirect("/")

        except stripe.error.APIConnectionError as e:
            messages.error(self.request, "Network Connection Error")
            return redirect("/")

        except stripe.error.StripeError as e:
            messages.error(
                self.request, "Something went wrong, you were not charged, please try again")
            return redirect("/")

        except Exception as e:
            messages.error(
                self.request, "Error Occured, we have been notified")
            return redirect("/")


class ItemDetailView(DetailView):
    model = Item
    template_name = "product-page.html"


@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_Item, created = OrderItem.objects.get_or_create(
        item=item, user=request.user, ordered=False)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_Item.quantity += 1
            order_Item.save()
            messages.info(
                request, "This item quantity was updated in your Cart")
        else:
            order.items.add(order_Item)
            messages.info(request, "This item was added to your Cart")
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(
            user=request.user, ordered_date=ordered_date)
        order.items.add(order_Item)
        messages.info(request, "This item was added to your Cart")
    return redirect("core:product_page", slug=slug)


def add_single_item_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_Item, created = OrderItem.objects.get_or_create(
        item=item, user=request.user, ordered=False)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_Item.quantity += 1
            order_Item.save()
            messages.info(
                request, "This item quantity was updated in your Cart")
        else:
            order.items.add(order_Item)
            messages.info(request, "This item was added to your Cart")
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(
            user=request.user, ordered_date=ordered_date)
        order.items.add(order_Item)
        messages.info(request, "This item was added to your Cart")
    return redirect("core:order-summary")


@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)

    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item, user=request.user, ordered=False)[0]
            order.items.remove(order_item)
            messages.info(request, "This item was removed your Cart")
            return redirect("core:order-summary")

        else:
            messages.info(request, "This item was not in your Cart")
            return redirect("core:product_page", slug=slug)
    else:
        messages.info(request, "You do not have an active order")
        return redirect("core:product_page", slug=slug)

    return redirect("core:product_page", slug=slug)


@login_required
def remove_single_item_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)

    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item, user=request.user, ordered=False)[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else:
                order.items.remove(order_item)
            messages.info(request, "This item was updated")
            return redirect("core:order-summary")
        else:
            messages.info(request, "This item was not in your Cart")
            return redirect("core:product_page", slug=slug)
    else:
        messages.info(request, "You do not have an active order")
        return redirect("core:product_page", slug=slug)

    return redirect("core:product_page", slug=slug)


def get_coupon(request, code):
    try:
        coupon = Coupon.objects.get(code=code)
        return coupon
    except ObjectDoesNotExist:
        messages.info(request, "Coupon does not exist")
        return redirect("core:checkout")


def add_coupon(request):
    if request.method == "POST":
        form = CouponForm(request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data.get("code")
                order = Order.objects.get(user=request.user, ordered=False)
                order.coupon = get_coupon(request, code)
                order.save()
                messages.success(request, "Coupon Successfully added")
                return redirect("core:checkout")

            except ObjectDoesNotExist:
                messages.info(request, "You do not have an active order")
                return redirect("core:checkout")
        return redirect("core:checkout")
    else:
        messages.warning(request, "Access denied")
        return redirect("core:item_list")


class RefundFormView(View):
    def get(self, *args, **kwargs):
        form = RefundForm()
        context = {
            "form": form
        }
        return render(self.request, "request_refund.html", context)

    def post(self, *args, **kwargs):
        form = RefundForm(self.request.POST)
        if form.is_valid():
            ref_code = form.cleaned_data.get("ref_code")
            message = form.cleaned_data.get("message")
            email = form.cleaned_data.get("email")

        try:
            order = Order.objects.get(ref_code=ref_code)
            order.refund_requested = True
            order.save()

            refund = Refund()
            refund.order = order
            refund.reason = message
            refund.email = email
            refund.save()

            messages.info(self.request, "Your request was received")
            return redirect("core:request-refund")

        except ObjectDoesNotExist:
            messages.info(self.request, "This order does not exist")
            return redirect("core:request-refund")
