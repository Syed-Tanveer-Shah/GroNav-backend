"""
Gro.Nav Email Notification Service
===================================
All emails are sent asynchronously (Thread) so API responses are never delayed.
All failures are caught and logged — the API will NEVER crash due to email issues.

Usage example:
    from .email_service import send_welcome_email
    Thread(target=send_welcome_email, args=(user,)).start()
"""

import logging
from threading import Thread
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


# ─── Shared HTML helpers ──────────────────────────────────────────────────────

def _base_template(content: str, preheader: str = '') -> str:
    """Wrap content in the standard Gro.Nav branded HTML shell."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Gro.Nav</title>
</head>
<body style="margin:0;padding:0;background-color:#f5f5f5;font-family:Arial,Helvetica,sans-serif;">
  {'<div style="display:none;max-height:0;overflow:hidden;">' + preheader + '</div>' if preheader else ''}
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f5f5;padding:30px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0"
               style="background:#ffffff;border-radius:12px;overflow:hidden;
                      box-shadow:0 4px 20px rgba(0,0,0,0.08);max-width:600px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#4CAF50 0%,#2e7d32 100%);
                        padding:28px 40px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:800;
                          letter-spacing:-0.5px;">🥦 Gro.Nav</h1>
              <p style="margin:6px 0 0;color:#c8e6c9;font-size:13px;letter-spacing:1px;
                         text-transform:uppercase;">Pakistan's Smart Grocery Platform</p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:36px 40px;">
              {content}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#f9f9f9;border-top:1px solid #e8e8e8;
                        padding:24px 40px;text-align:center;">
              <p style="margin:0 0 6px;color:#888;font-size:12px;">
                © 2025 Gro.Nav &nbsp;|&nbsp; Pakistan's Smart Grocery Comparison Platform
              </p>
              <p style="margin:0;color:#bbb;font-size:11px;">
                This is an automated email — please do not reply directly.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _green_button(text: str, href: str = '#') -> str:
    return (
        f'<div style="text-align:center;margin:28px 0;">'
        f'<a href="{href}" style="background:#4CAF50;color:#ffffff;text-decoration:none;'
        f'padding:14px 36px;border-radius:8px;font-size:15px;font-weight:700;'
        f'display:inline-block;letter-spacing:0.3px;">{text}</a></div>'
    )


def _order_table(order) -> str:
    """Render a styled order-summary table from a CustomerOrder instance."""
    subtotal = float(order.price_per_item) * int(order.quantity)
    delivery = float(order.delivery_fee)
    platform = float(order.platform_fee)
    total    = float(order.total_amount)

    return f"""
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border-collapse:collapse;margin:20px 0;border-radius:8px;overflow:hidden;
                  border:1px solid #e8f5e9;">
      <thead>
        <tr style="background:#4CAF50;">
          <th style="color:#fff;padding:12px 16px;text-align:left;font-size:13px;">Product</th>
          <th style="color:#fff;padding:12px 16px;text-align:center;font-size:13px;">Qty</th>
          <th style="color:#fff;padding:12px 16px;text-align:right;font-size:13px;">Unit Price</th>
          <th style="color:#fff;padding:12px 16px;text-align:right;font-size:13px;">Subtotal</th>
        </tr>
      </thead>
      <tbody>
        <tr style="background:#f9fbe7;">
          <td style="padding:14px 16px;font-size:14px;color:#333;">{order.product_name}</td>
          <td style="padding:14px 16px;font-size:14px;color:#333;text-align:center;">{order.quantity}</td>
          <td style="padding:14px 16px;font-size:14px;color:#333;text-align:right;">
              Rs. {float(order.price_per_item):,.0f}</td>
          <td style="padding:14px 16px;font-size:14px;color:#333;text-align:right;">
              Rs. {subtotal:,.0f}</td>
        </tr>
        <tr style="background:#ffffff;">
          <td colspan="3" style="padding:10px 16px;font-size:13px;color:#666;">
              🚚 Delivery Fee</td>
          <td style="padding:10px 16px;font-size:13px;color:#666;text-align:right;">
              Rs. {delivery:,.0f}</td>
        </tr>
        <tr style="background:#f9fbe7;">
          <td colspan="3" style="padding:10px 16px;font-size:13px;color:#666;">
              🏷️ Platform Fee</td>
          <td style="padding:10px 16px;font-size:13px;color:#666;text-align:right;">
              Rs. {platform:,.0f}</td>
        </tr>
        <tr style="background:#e8f5e9;">
          <td colspan="3" style="padding:14px 16px;font-size:15px;font-weight:700;color:#2e7d32;">
              💰 Total Amount</td>
          <td style="padding:14px 16px;font-size:15px;font-weight:700;color:#2e7d32;text-align:right;">
              Rs. {total:,.0f}</td>
        </tr>
      </tbody>
    </table>"""


def _delivery_eta(order) -> str:
    """Return estimated delivery time string based on city match."""
    try:
        store_city    = (order.store.city or '').strip().lower() if order.store else ''
        delivery_addr = (order.delivery_address or '').strip().lower()
        if store_city and store_city in delivery_addr:
            return '2–3 business days'
    except Exception:
        pass
    return '5–6 business days'


def _send_async(fn, *args):
    """Fire-and-forget: run fn(*args) in a daemon thread."""
    t = Thread(target=fn, args=args, daemon=True)
    t.start()


# ─── 1. Welcome Email ─────────────────────────────────────────────────────────

def _do_send_welcome_email(user):
    try:
        name = user.get_full_name() or user.username or user.email.split('@')[0]
        content = f"""
        <h2 style="color:#2e7d32;margin:0 0 8px;">Welcome to Gro.Nav, {name}! 🎉</h2>
        <p style="color:#555;font-size:15px;line-height:1.7;margin:0 0 20px;">
          Thank you for joining <strong>Gro.Nav</strong> — Pakistan's smart grocery
          comparison platform. We're thrilled to have you on board!
        </p>

        <div style="background:#e8f5e9;border-left:4px solid #4CAF50;border-radius:6px;
                     padding:18px 20px;margin:20px 0;">
          <p style="margin:0 0 10px;font-weight:700;color:#2e7d32;font-size:14px;">
              ✨ What you can do with Gro.Nav:
          </p>
          <ul style="margin:0;padding-left:20px;color:#444;font-size:14px;line-height:1.8;">
            <li>🛒 Compare grocery prices across stores in Pakistan</li>
            <li>📍 Find products near your location instantly</li>
            <li>💰 Save money with smart price comparisons</li>
            <li>⚡ Order directly from your favourite local stores</li>
          </ul>
        </div>

        {_green_button('🛒 Start Shopping', 'http://localhost:3000')}

        <p style="color:#888;font-size:13px;text-align:center;margin-top:10px;">
          Happy shopping! The Gro.Nav Team 🥦
        </p>"""

        html = _base_template(content, preheader=f'Welcome to Gro.Nav, {name}!')
        send_mail(
            subject='Welcome to Gro.Nav! 🎉',
            message=f'Welcome to Gro.Nav, {name}! Thank you for joining Pakistan\'s smart grocery platform.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html,
            fail_silently=False,
        )
        logger.info(f'[EMAIL] Welcome email sent to {user.email}')
    except Exception as e:
        logger.error(f'[EMAIL] Failed to send welcome email to {getattr(user, "email", "?")} — {e}')


def send_welcome_email(user):
    """Async welcome email after user registration."""
    _send_async(_do_send_welcome_email, user)


# ─── 2. Order Confirmation (placed) ──────────────────────────────────────────

def _do_send_order_confirmation_email(order):
    try:
        name    = order.customer_name or order.customer.get_full_name() or 'Valued Customer'
        eta     = _delivery_eta(order)
        payment = 'Stripe (Card)' if order.payment_method == 'stripe' else 'Cash on Delivery (COD)'

        content = f"""
        <h2 style="color:#2e7d32;margin:0 0 4px;">Order Confirmed! ✅</h2>
        <p style="color:#555;font-size:15px;margin:0 0 20px;">
          Thank you for your order, <strong>{name}</strong>!
          Your order has been placed successfully.
        </p>

        <div style="background:#f1f8e9;border-radius:8px;padding:16px 20px;margin-bottom:20px;">
          <p style="margin:0;font-size:14px;color:#555;">
            📦 <strong>Order #</strong>{order.order_id} &nbsp;|&nbsp;
            💳 <strong>Payment:</strong> {payment}
          </p>
          <p style="margin:8px 0 0;font-size:14px;color:#555;">
            📍 <strong>Delivery to:</strong> {order.delivery_address}
          </p>
          <p style="margin:8px 0 0;font-size:14px;color:#555;">
            🕐 <strong>Estimated Delivery:</strong> {eta}
          </p>
        </div>

        {_order_table(order)}

        <div style="background:#fff3e0;border-radius:8px;padding:14px 18px;margin-top:16px;">
          <p style="margin:0;font-size:14px;color:#e65100;">
            ⏳ Your seller will confirm your order shortly.
            You will receive another email when the order status is updated.
          </p>
        </div>

        {_green_button('📦 Track My Order', 'http://localhost:3000')}"""

        html = _base_template(content, preheader=f'Order #{order.order_id} confirmed!')
        send_mail(
            subject=f'Order Confirmed! Order #{order.order_id} — Gro.Nav',
            message=f'Your order #{order.order_id} for {order.product_name} has been confirmed.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.customer.email],
            html_message=html,
            fail_silently=False,
        )
        logger.info(f'[EMAIL] Order confirmation sent → {order.customer.email} (Order #{order.order_id})')
    except Exception as e:
        logger.error(f'[EMAIL] Failed order confirmation email (Order #{getattr(order, "order_id", "?")}) — {e}')


def send_order_confirmation_email(order):
    """Async order confirmation email after order is created."""
    _send_async(_do_send_order_confirmation_email, order)


# ─── 3. Order Received by Seller ─────────────────────────────────────────────

def _do_send_order_received_by_seller_email(order):
    try:
        name       = order.customer_name or order.customer.get_full_name() or 'Valued Customer'
        store_name = order.store.name if order.store else 'the seller'
        eta        = _delivery_eta(order)

        content = f"""
        <h2 style="color:#2e7d32;margin:0 0 4px;">Great News! Your Order Was Received 🎉</h2>
        <p style="color:#555;font-size:15px;margin:0 0 20px;">
          Hi <strong>{name}</strong>! <strong>{store_name}</strong> has received
          your order and is now processing it.
        </p>

        <div style="background:#f1f8e9;border-radius:8px;padding:16px 20px;margin-bottom:20px;">
          <p style="margin:0;font-size:14px;color:#555;">
            📦 <strong>Order #</strong>{order.order_id} &nbsp;|&nbsp;
            🏪 <strong>Store:</strong> {store_name}
          </p>
          <p style="margin:8px 0 0;font-size:14px;color:#555;">
            📍 <strong>Delivery to:</strong> {order.delivery_address}
          </p>
          <p style="margin:8px 0 0;font-size:14px;color:#555;">
            🕐 <strong>Estimated Delivery:</strong> {eta}
          </p>
          <p style="margin:8px 0 0;font-size:14px;color:#2e7d32;font-weight:700;">
            ✅ <strong>Status:</strong> Received by Seller
          </p>
        </div>

        {_order_table(order)}"""

        html = _base_template(content, preheader=f'Order #{order.order_id} received by {store_name}')
        send_mail(
            subject=f'Your Order #{order.order_id} has been Received! — Gro.Nav',
            message=f'Your order #{order.order_id} has been received by {store_name}.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.customer.email],
            html_message=html,
            fail_silently=False,
        )
        logger.info(f'[EMAIL] Order received email sent → {order.customer.email} (Order #{order.order_id})')
    except Exception as e:
        logger.error(f'[EMAIL] Failed order received email (Order #{getattr(order, "order_id", "?")}) — {e}')


def send_order_received_by_seller_email(order):
    """Async email when seller first receives the order."""
    _send_async(_do_send_order_received_by_seller_email, order)


# ─── 4. Order Packed ─────────────────────────────────────────────────────────

def _do_send_order_packed_email(order):
    try:
        name = order.customer_name or order.customer.get_full_name() or 'Valued Customer'

        content = f"""
        <h2 style="color:#2e7d32;margin:0 0 4px;">Your Order is Packed! 📦</h2>
        <p style="color:#555;font-size:15px;margin:0 0 20px;">
          Hi <strong>{name}</strong>! Your order has been carefully packed and
          is now ready for pickup by the delivery partner.
        </p>

        <div style="background:#f1f8e9;border-radius:8px;padding:16px 20px;margin-bottom:20px;">
          <p style="margin:0;font-size:14px;color:#555;">
            📦 <strong>Order #</strong>{order.order_id}
          </p>
          <p style="margin:8px 0 0;font-size:14px;color:#555;">
            📍 <strong>Delivery to:</strong> {order.delivery_address}
          </p>
          <p style="margin:8px 0 0;font-size:14px;color:#1976d2;font-weight:700;">
            📦 <strong>Status:</strong> Packed — Awaiting Pickup
          </p>
          <p style="margin:8px 0 0;font-size:14px;color:#555;">
            🚚 <strong>Expected Delivery:</strong> 1–2 days
          </p>
        </div>

        {_order_table(order)}

        <p style="color:#555;font-size:14px;text-align:center;">
          Sit tight — your groceries are on their way soon! 🥦
        </p>"""

        html = _base_template(content, preheader=f'Order #{order.order_id} has been packed!')
        send_mail(
            subject=f'Your Order #{order.order_id} is Packed! 📦 — Gro.Nav',
            message=f'Your order #{order.order_id} has been packed and is ready for pickup.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.customer.email],
            html_message=html,
            fail_silently=False,
        )
        logger.info(f'[EMAIL] Order packed email sent → {order.customer.email} (Order #{order.order_id})')
    except Exception as e:
        logger.error(f'[EMAIL] Failed order packed email (Order #{getattr(order, "order_id", "?")}) — {e}')


def send_order_packed_email(order):
    """Async email when order status changes to 'packed'."""
    _send_async(_do_send_order_packed_email, order)


# ─── 5. Out for Delivery ──────────────────────────────────────────────────────

def _do_send_order_out_for_delivery_email(order):
    try:
        name = order.customer_name or order.customer.get_full_name() or 'Valued Customer'

        content = f"""
        <h2 style="color:#2e7d32;margin:0 0 4px;">Your Order is Out for Delivery! 🚚</h2>
        <p style="color:#555;font-size:15px;margin:0 0 20px;">
          Hi <strong>{name}</strong>! Your order is on its way.
          Our delivery partner is heading to your location right now!
        </p>

        <div style="background:#e3f2fd;border-radius:8px;padding:16px 20px;margin-bottom:20px;
                     border-left:4px solid #1976d2;">
          <p style="margin:0;font-size:14px;color:#555;">
            🚚 <strong>Order #</strong>{order.order_id}
          </p>
          <p style="margin:8px 0 0;font-size:14px;color:#555;">
            📍 <strong>Delivering to:</strong> {order.delivery_address}
          </p>
          <p style="margin:8px 0 0;font-size:14px;color:#1565c0;font-weight:700;">
            🚚 <strong>Status:</strong> Out for Delivery
          </p>
        </div>

        {_order_table(order)}

        <div style="background:#fff8e1;border-radius:8px;padding:14px 18px;margin-top:16px;">
          <p style="margin:0;font-size:14px;color:#f57f17;">
            ⚠️ Please be available at <strong>{order.delivery_address}</strong>
            to receive your order. Keep your phone reachable for the delivery partner.
          </p>
        </div>"""

        html = _base_template(content, preheader=f'Order #{order.order_id} is out for delivery!')
        send_mail(
            subject=f'Your Order #{order.order_id} is Out for Delivery! 🚚 — Gro.Nav',
            message=f'Your order #{order.order_id} is out for delivery to {order.delivery_address}.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.customer.email],
            html_message=html,
            fail_silently=False,
        )
        logger.info(f'[EMAIL] Out-for-delivery email sent → {order.customer.email} (Order #{order.order_id})')
    except Exception as e:
        logger.error(f'[EMAIL] Failed out-for-delivery email (Order #{getattr(order, "order_id", "?")}) — {e}')


def send_order_out_for_delivery_email(order):
    """Async email when order status changes to 'out_for_delivery'."""
    _send_async(_do_send_order_out_for_delivery_email, order)


# ─── 6. Order Delivered ───────────────────────────────────────────────────────

def _do_send_order_delivered_email(order):
    try:
        name = order.customer_name or order.customer.get_full_name() or 'Valued Customer'

        content = f"""
        <h2 style="color:#2e7d32;margin:0 0 4px;">Order Delivered Successfully! ✅</h2>
        <p style="color:#555;font-size:15px;margin:0 0 20px;">
          Hi <strong>{name}</strong>! Your order has been delivered.
          We hope you enjoy your groceries! 🎉
        </p>

        <div style="background:#e8f5e9;border-radius:8px;padding:16px 20px;margin-bottom:20px;
                     border-left:4px solid #4CAF50;">
          <p style="margin:0;font-size:14px;color:#555;">
            ✅ <strong>Order #</strong>{order.order_id} — Delivered
          </p>
          <p style="margin:8px 0 0;font-size:14px;color:#555;">
            📍 <strong>Delivered to:</strong> {order.delivery_address}
          </p>
          <p style="margin:8px 0 0;font-size:14px;color:#2e7d32;font-weight:700;">
            ✅ <strong>Status:</strong> Delivered
          </p>
        </div>

        {_order_table(order)}

        <div style="background:#f3e5f5;border-radius:8px;padding:18px 20px;margin-top:20px;
                     text-align:center;">
          <p style="margin:0 0 8px;font-size:15px;color:#6a1b9a;font-weight:700;">
            ⭐ How was your experience?
          </p>
          <p style="margin:0 0 16px;font-size:14px;color:#555;">
            Your feedback helps us improve and helps other shoppers make better decisions.
          </p>
          {_green_button('⭐ Rate Your Experience', 'http://localhost:3000')}
        </div>

        <p style="color:#888;font-size:13px;text-align:center;margin-top:20px;">
          Thank you for shopping with Gro.Nav! 🥦
        </p>"""

        html = _base_template(content, preheader=f'Order #{order.order_id} has been delivered!')
        send_mail(
            subject=f'Order #{order.order_id} Delivered Successfully! ✅ — Gro.Nav',
            message=f'Your order #{order.order_id} has been delivered. Thank you for shopping with Gro.Nav!',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.customer.email],
            html_message=html,
            fail_silently=False,
        )
        logger.info(f'[EMAIL] Delivered email sent → {order.customer.email} (Order #{order.order_id})')
    except Exception as e:
        logger.error(f'[EMAIL] Failed delivered email (Order #{getattr(order, "order_id", "?")}) — {e}')


def send_order_delivered_email(order):
    """Async email when order status changes to 'delivered'."""
    _send_async(_do_send_order_delivered_email, order)


# ─── 7. Seller Dashboard Notification (not email) ────────────────────────────

def send_verification_complete_seller_notification(order):
    """
    Creates a SellerNotification in the database for the seller when the buyer
    confirms receipt (order is marked 'delivered').
    This appears in the seller dashboard notification bell icon.
    """
    try:
        from ..services.products.seller_models import SellerNotification
        seller = None
        if order.store and hasattr(order.store, 'seller') and order.store.seller:
            seller = order.store.seller
        elif order.seller and hasattr(order.seller, 'seller'):
            seller = order.seller.seller

        if not seller:
            logger.warning(f'[NOTIFICATION] No seller found for Order #{order.order_id}')
            return

        SellerNotification.objects.create(
            seller=seller,
            type='verification',
            title='Buyer Confirmed Receipt',
            message=(
                f'✅ Buyer has confirmed receipt of Order #{order.order_id}'
                f' — {order.product_name}'
            ),
        )
        logger.info(f'[NOTIFICATION] Seller notification created for Order #{order.order_id}')
    except Exception as e:
        logger.error(
            f'[NOTIFICATION] Failed to create seller notification '
            f'(Order #{getattr(order, "order_id", "?")}) — {e}'
        )
