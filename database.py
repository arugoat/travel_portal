import mysql.connector
from datetime import datetime
import hashlib
import os
import streamlit as st

class Database:
    def __init__(self):
        self.conn = mysql.connector.connect(
            host="localhost",
            user="root",  # Replace with your MySQL username
            password="Aryan0203",  # Replace with your MySQL password
            database="dbms_otps_project"
        )
        self.cursor = self.conn.cursor(dictionary=True)
    
    def __del__(self):
        self.conn.close()

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def authenticate_user(self, username, password, role):
        hashed_password = self.hash_password(password)
        query = "SELECT * FROM user WHERE username = %s AND password = %s AND role = %s"
        self.cursor.execute(query, (username, hashed_password, role))
        return self.cursor.fetchone()

    def register_user(self, username, password, role):
        try:
            hashed_password = self.hash_password(password)
            query = "INSERT INTO user (username, password, role) VALUES (%s, %s, %s)"
            self.cursor.execute(query, (username, hashed_password, role))
            self.conn.commit()
            return True
        except mysql.connector.Error as err:
            print(f"Error: {err}")
            return False

    def get_flights(self):
        self.cursor.execute("SELECT * FROM flight WHERE availability > 0")
        return self.cursor.fetchall()

    def get_accommodations(self):
        self.cursor.execute("SELECT * FROM accommodation WHERE availability > 0")
        return self.cursor.fetchall()

    def create_booking(self, booking_type, user_id, price, flight_id=None, accommodation_id=None):
        try:
            # Ensure the price is a decimal
            price = float(price) if isinstance(price, str) else price

            # Begin transaction
            self.cursor.execute("START TRANSACTION")
        
            # Check availability first
            if booking_type == 'flight' and flight_id:
                self.cursor.execute(
                    "SELECT availability FROM flight WHERE flightId = %s FOR UPDATE",
                    (flight_id,)
                )
                result = self.cursor.fetchone()
                if not result or result['availability'] <= 0:
                    self.cursor.execute("ROLLBACK")
                    return False
                
            elif booking_type == 'accommodation' and accommodation_id:
                self.cursor.execute(
                    "SELECT availability FROM accommodation WHERE accommodationId = %s FOR UPDATE",
                    (accommodation_id,)
                )
                result = self.cursor.fetchone()
                if not result or result['availability'] <= 0:
                    self.cursor.execute("ROLLBACK")
                    return False

            # Create the booking
            query = """INSERT INTO booking 
                      (type, userId, price, flightId, accommodationId, status, booking_date) 
                      VALUES (%s, %s, %s, %s, %s, 'Confirmed', NOW())"""
            self.cursor.execute(query, (
                booking_type, 
                user_id, 
                price, 
                flight_id if booking_type == 'flight' else None,
                accommodation_id if booking_type == 'accommodation' else None
            ))

            # Let the trigger handle availability updates
            pass


            self.cursor.execute("COMMIT")
            return True

        except mysql.connector.Error as err:
            print(f"Database error: {err}")
            self.cursor.execute("ROLLBACK")
            return False

    def get_last_booking_id(self):
        try:
            self.cursor.execute("""
                SELECT bookingId 
                FROM booking 
                WHERE userId = %s 
                ORDER BY booking_date DESC 
                LIMIT 1
                """, (st.session_state.user_id,))
            result = self.cursor.fetchone()
            return result['bookingId'] if result else None
        except mysql.connector.Error as err:
            print(f"Error getting last booking ID: {err}")
            return None


    def create_payment(self, payment_type, bank_name, user_id, booking_id, price):
        try:
            query = """INSERT INTO payment 
                      (typeOfPayment, bankName, userId, bookingId, price) 
                      VALUES (%s, %s, %s, %s, %s)"""
            self.cursor.execute(query, 
                              (payment_type, bank_name, user_id, booking_id, price))
            self.conn.commit()
            return True
        except mysql.connector.Error as err:
            print(f"Error: {err}")
            return False

    def get_all_bookings(self):
        self.cursor.execute("SELECT * FROM booking")
        return self.cursor.fetchall()

    def get_bookings_by_type(self, booking_type):
        query = "SELECT * FROM booking WHERE type = %s"
        self.cursor.execute(query, (booking_type,))
        return self.cursor.fetchall()

    def delete_booking(self, booking_id):
        try:
            query = "DELETE FROM booking WHERE bookingId = %s"
            self.cursor.execute(query, (booking_id,))
            self.conn.commit()
            return True
        except mysql.connector.Error as err:
            print(f"Error: {err}")
            return False

    def get_all_payments(self):
        self.cursor.execute("SELECT * FROM payment")
        return self.cursor.fetchall()

    def username_exists(self, username):
        query = "SELECT COUNT(*) as count FROM user WHERE username = %s"
        self.cursor.execute(query, (username,))
        result = self.cursor.fetchone()
        return result['count'] > 0
    


        # Advanced Search Methods
    def search_flights(self, departure=None, destination=None, 
                      min_price=None, max_price=None, departure_date=None):
        self.cursor.callproc('SearchFlights', 
                           (departure, destination, min_price, max_price, departure_date))
        for result in self.cursor.stored_results():
            return result.fetchall()
        return []

    def search_accommodations(self, location=None, min_price=None, 
                            max_price=None, checkin_date=None, checkout_date=None):
        self.cursor.callproc('SearchAccommodations', 
                           (location, min_price, max_price, checkin_date, checkout_date))
        for result in self.cursor.stored_results():
            return result.fetchall()
        return []

    # Analytics Methods
    def get_revenue_analytics(self):
        self.cursor.callproc('GetRevenueAnalytics')
        for result in self.cursor.stored_results():
            return result.fetchall()
        return []

    def get_popular_destinations(self):
        self.cursor.callproc('GetPopularDestinations')
        for result in self.cursor.stored_results():
            return result.fetchall()
        return []

    def get_customer_analytics(self, user_id):
        self.cursor.callproc('GetCustomerAnalytics', (user_id,))
        for result in self.cursor.stored_results():
            return result.fetchone()
        return None

    # Detailed Booking Views
    def get_booking_details(self, booking_id=None):
        if booking_id:
            query = "SELECT * FROM booking_details WHERE bookingId = %s"
            self.cursor.execute(query, (booking_id,))
            return self.cursor.fetchone()
        else:
            self.cursor.execute("SELECT * FROM booking_details")
            return self.cursor.fetchall()

    def get_user_booking_history(self, user_id):
        query = """
        SELECT * FROM booking_details 
        WHERE username = (SELECT username FROM user WHERE userId = %s)
        ORDER BY booking_date DESC
        """
        self.cursor.execute(query, (user_id,))
        return self.cursor.fetchall()

    # Aggregation Methods
    def get_booking_stats(self):
        query = """
        SELECT 
            COUNT(*) as total_bookings,
            SUM(CASE WHEN type = 'flight' THEN 1 ELSE 0 END) as flight_bookings,
            SUM(CASE WHEN type = 'accommodation' THEN 1 ELSE 0 END) as accommodation_bookings,
            SUM(price) as total_revenue,
            AVG(price) as avg_booking_value
        FROM booking 
        WHERE status != 'Cancelled'
        """
        self.cursor.execute(query)
        return self.cursor.fetchone()

    def get_monthly_stats(self):
        query = """
        SELECT 
            DATE_FORMAT(booking_date, '%Y-%m') as month,
            COUNT(*) as total_bookings,
            SUM(price) as total_revenue,
            AVG(price) as avg_booking_value
        FROM booking
        WHERE status != 'Cancelled'
        GROUP BY DATE_FORMAT(booking_date, '%Y-%m')
        ORDER BY month DESC
        LIMIT 12
        """
        self.cursor.execute(query)
        return self.cursor.fetchall()

    def get_admin_user_revenue_analysis(self):
        query = """
        SELECT 
            u.userId,
            u.username,
            u.role,
            COUNT(b.bookingId) AS total_bookings,
            COALESCE(SUM(b.price), 0) AS total_revenue,
            COALESCE(AVG(b.price), 0) AS avg_booking_value,
            MAX(b.booking_date) AS last_booking_date,
            COUNT(DISTINCT CASE WHEN b.type = 'flight' THEN b.bookingId END) AS flight_bookings,
            COUNT(DISTINCT CASE WHEN b.type = 'accommodation' THEN b.bookingId END) AS accommodation_bookings
        FROM 
            user u
        LEFT JOIN 
            booking b ON u.userId = b.userId
        GROUP BY 
            u.userId, u.username, u.role
        ORDER BY 
            total_revenue DESC
        """
        self.cursor.execute(query)
        return self.cursor.fetchall()