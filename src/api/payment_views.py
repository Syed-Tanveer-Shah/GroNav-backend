import os
import stripe
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

# Load the Stripe secret key from environment variable
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')


class CreatePaymentIntentView(APIView):
    """
    POST /api/payment/create-payment-intent
    Body: { "amount": <number in Rs.> }
    Returns: { "clientSecret": "..." }

    NOTE: Stripe requires amounts in the smallest currency unit.
    For PKR (Pakistani Rupee), Stripe treats it as a zero-decimal currency,
    so we pass the amount directly (NOT multiplied by 100).
    However, as per project requirement, we multiply by 100 to be safe
    in case Stripe processes PKR as a decimal currency in test mode.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            amount = request.data.get('amount')

            if amount is None:
                return Response({'error': 'Amount is required.'}, status=400)

            try:
                amount = int(float(amount))
            except (ValueError, TypeError):
                return Response({'error': 'Invalid amount value.'}, status=400)

            if amount <= 0:
                return Response({'error': 'Amount must be greater than zero.'}, status=400)

            # Convert to smallest unit (paise/cents) — multiply by 100
            amount_in_smallest_unit = amount * 100

            # Create Stripe PaymentIntent
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_in_smallest_unit,
                currency='pkr',  # Pakistani Rupee
                payment_method_types=['card'],
                metadata={
                    'source': 'CartGo-FYP',
                }
            )

            return Response({'clientSecret': payment_intent.client_secret}, status=200)

        except stripe.error.StripeError as e:
            return Response({'error': str(e.user_message)}, status=400)
        except Exception as e:
            return Response({'error': f'Server error: {str(e)}'}, status=500)
