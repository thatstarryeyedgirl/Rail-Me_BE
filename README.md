# Rail_Me_BE

## Overview
**Rail-me** is a train service provider that commutes passengers from the **Abeokuta region** to the **Northern part of Nigeria**.  
This RESTful API was designed to help the management transition from a **manual paper booking system** to a **fully digitized platform** — ensuring seamless ticket reservations, authentication, and user management. 
It provides a **RESTful API** for both **commuters** and **administrators** to interact with the system.
- Commuters can register, verify their accounts via OTP, and book train seats.
- Admins can manage users, upload new train reservations, and track overall booking statistics.

All endpoints are **secured with JWT authentication**, except for **signup** and **login**.

## Features
### Commuters (Users)
- Sign up using **Email**, **Phone Number**, **First Name**, **Last Name**, and **Password**
- Receive OTP verification via **Email** or **Phone Number**
- Reset or recover forgotten passwords
- Log in securely using **Email** and **Password**
- Book a train seat
- Edit (reschedule) existing bookings
- Cancel (delete) bookings
- View all available train services (**Reservation**, **Business**, or **Economy class**)

### Admin
- View all registered commuters
- Upload new train reservations (with train and coach images)
- View total number of bookings on the platform

## Tech Stack
- **Backend Framework:** Django & Django REST Framework (DRF)
- **Authentication:** JWT (via `djangorestframework-simplejwt`)
- **Database:** PostgreSQL (for development)
- **Language:** Python 3.12.10
- **Environment Management:** `.env`
# Rail-Me_BE
