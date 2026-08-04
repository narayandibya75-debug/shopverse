# Forever FBO E-Commerce — PRD

## Original Problem Statement
"i want to make an E-commerce website which will work as like flipkart, amazon for my forever business as AN FBO i want to sell products through that site provide me bakend(fastapi) and frontend for that which will have the same features like flipkart and amazon. The site should strictly follow forever guidelines. also as an FBO i able to add the product which will be not available or is been ended."

## User Choices
- Auth: Both (JWT email+password + Emergent Google social login)
- Payments: Razorpay (MOCKED — keys not provided; mocked checkout/verify flow)
- Role model: Customer storefront + FBO Admin Panel
- Images: Upload via Emergent Object Storage
- Forever compliance: Yes — official categories + BV/CC fields + MRP

## Personas
- **Customer**: browses/buys authentic Forever products, tracks orders
- **FBO Admin**: manages products (add/edit/delete), status (active/out_of_stock/discontinued), manages orders

## Core Requirements (static)
- Forever-style categories (Aloe Drinks, Bee Products, Personal Care, Nutrition, Weight Management, Skincare)
- Products with MRP, price, BV, CC, stock, status, images
- Shopping cart + checkout with address + (mocked) Razorpay
- Admin dashboard with stats, product CRUD with image upload, order management
- Email/password auth + Google social login

## What's Been Implemented (Feb 2026)
- FastAPI backend: auth, products, cart, orders, checkout (UPI QR + manual UTR verification by admin), admin endpoints, object storage upload
- Auto-seed: admin user + 12 sample Forever products
- React frontend: Home, Shop (filters+search), Product Detail, Cart (drawer + page), Checkout (2-step UPI QR), Orders, Login, Register, Google OAuth callback, Admin panel (Dashboard, Products, Orders with verify/reject UTR)
- Shadcn UI + Forever brand theme (Deep Aloe Green + Honey Gold, Outfit + DM Sans)
- data-testid on all interactive elements
- Site is LIVE at https://forever-ecommerce.preview.emergentagent.com (deployed Apr 2026)
- UPI QR payment: 7978765224@paytm / FBO PAYMENT GATEWAY (replaces mocked Razorpay)

## Backlog (P1/P2)
- Real Razorpay keys & live payment verification (currently MOCKED)
- Product reviews & ratings
- Wishlist / save for later
- Email notifications (order confirmed/shipped)
- Coupon codes & FBO-specific discount rules
- Multi-address book
- Inventory auto-decrement on order
- Order invoice PDF with BV/CC totals
- FBO downline / referral tracking

## Next Action Items
- Collect real Razorpay keys from user to replace MOCKED flow
- E2E testing via testing_agent_v3
