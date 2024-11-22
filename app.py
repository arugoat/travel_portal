import streamlit as st
from database import Database
import time
import pandas as pd
from PIL import Image
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from decimal import Decimal
import logging
import streamlit as st

#back to default black

# Initialize database
db = Database()

# Initialize session state variables
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'role' not in st.session_state:
    st.session_state.role = None
if 'show_payment' not in st.session_state:
    st.session_state.show_payment = False
if 'payment_success' not in st.session_state:
    st.session_state.payment_success = False
if 'booking_step' not in st.session_state:
    st.session_state.booking_step = 'search'  # Possible values: 'search', 'select', 'payment'
if 'selected_item' not in st.session_state:
    st.session_state.selected_item = None

def format_price(price):
    if price is None:
        return "₹0.00"
    return f"₹{float(price):,.2f}"

def login_signup_page():
    st.title("Welcome to Travel Booking System")
    st.image("travel.jpg", width=300)
    
    tab1, tab2 = st.tabs(["Sign In", "Sign Up"])
    
    with tab1:
        role = st.selectbox("Select Role", ["customer", "admin"], key='signin_role')
        username = st.text_input("Username", key='signin_username')
        password = st.text_input("Password", type='password', key='signin_password')
        
        if st.button("Sign In"):
            user = db.authenticate_user(username, password, role)
            if user:
                st.session_state.logged_in = True
                st.session_state.user_id = user['userId']
                st.session_state.role = user['role']
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid credentials!")

    with tab2:
        role = st.selectbox("Select Role", ["customer", "admin"], key='signup_role')
        username = st.text_input("Username", key='signup_username')
        password = st.text_input("Password", type='password', key='signup_password')
        
        if st.button("Sign Up"):
            if db.username_exists(username):
                st.error("Username already exists!")
            else:
                if db.register_user(username, password, role):
                    st.success("Registration successful! Please sign in.")
                else:
                    st.error("Registration failed!")

def show_customer_analytics():
    st.subheader("Your Booking Analytics")
    analytics = db.get_customer_analytics(st.session_state.user_id)
    
    if analytics:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Bookings", analytics.get('total_bookings', 0))
        with col2:
            st.metric("Total Spent", format_price(analytics.get('total_spent', 0)))
        with col3:
            avg_value = analytics.get('avg_booking_value', 0)
            st.metric("Average Booking Value", format_price(avg_value))

        col4, col5 = st.columns(2)
        with col4:
            st.metric("Flight Bookings", analytics.get('flight_bookings', 0))
        with col5:
            st.metric("Accommodation Bookings", analytics.get('accommodation_bookings', 0))
    else:
        st.info("No booking data available yet.")


def show_booking_history():
    st.subheader("Your Booking History")
    bookings = db.get_user_booking_history(st.session_state.user_id)
    
    if bookings:
        df = pd.DataFrame(bookings)
        df['amount'] = df['price'].apply(format_price)
        
        # Create an interactive table
        st.dataframe(
            df[['bookingId', 'type', 'amount', 'status', 'booking_date']],
            column_config={
                "booking_date": st.column_config.DatetimeColumn(
                    "Booking Date",
                    format="D MMM YYYY, h:mm a"
                )
            }
        )

def advanced_flight_search():
    st.subheader("Advanced Flight Search")
    
    # Only show search form if we're in search step
    if st.session_state.booking_step == 'search':
        col1, col2 = st.columns(2)
        with col1:
            departure = st.text_input("Departure Airport")
            min_price = st.number_input("Minimum Price", min_value=0.0, value=0.0)
        
        with col2:
            destination = st.text_input("Destination Airport")
            max_price = st.number_input("Maximum Price", min_value=0.0, value=0.0)
        
        departure_date = st.date_input("Departure Date")
        
        if st.button("Search Flights"):
            flights = db.search_flights(departure, destination, min_price, max_price, departure_date)
            if flights:
                st.session_state.available_flights = flights
                st.session_state.booking_step = 'select'
                st.rerun()
            else:
                st.info("No flights found matching your criteria.")
    
    # Show selection form if we're in select step
    elif st.session_state.booking_step == 'select':
        if 'available_flights' in st.session_state:
            df = pd.DataFrame(st.session_state.available_flights)
            df['price'] = df['price'].apply(format_price)
            st.dataframe(df)
            
            flight_id = st.number_input("Enter Flight ID to book:", min_value=1)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Book Selected Flight"):
                    selected_flight = next(
                        (f for f in st.session_state.available_flights 
                         if f['flightId'] == flight_id), None
                    )
                    
                    if selected_flight:
                        price = float(str(selected_flight['price']).replace('₹', '').replace(',', ''))
                        
                        booking_success = db.create_booking(
                            'flight',
                            st.session_state.user_id,
                            price,
                            flight_id=flight_id
                        )
                        
                        if booking_success:
                            booking_id = db.get_last_booking_id()
                            if booking_id:
                                st.session_state.current_booking = {
                                    'id': booking_id,
                                    'price': price
                                }
                                st.session_state.show_payment = True
                                st.session_state.booking_step = 'payment'
                                st.rerun()
                            else:
                                st.error("Failed to retrieve booking ID.")
                        else:
                            st.error("Failed to create booking. Please try again.")
                    else:
                        st.error("Please select a valid flight from the search results.")
            
            with col2:
                if st.button("Back to Search"):
                    st.session_state.booking_step = 'search'
                    if 'available_flights' in st.session_state:
                        del st.session_state.available_flights
                    st.rerun()

def advanced_accommodation_search():
    st.subheader("Advanced Accommodation Search")
    
    # Only show search form if we're in search step
    if st.session_state.booking_step == 'search':
        col1, col2 = st.columns(2)
        with col1:
            location = st.text_input("Location")
            min_price = st.number_input("Minimum Price", min_value=0, key="accom_min_price")
        with col2:
            max_price = st.number_input("Maximum Price", min_value=0, key="accom_max_price")
        
        col3, col4 = st.columns(2)
        with col3:
            checkin_date = st.date_input("Check-in Date")
        with col4:
            checkout_date = st.date_input("Check-out Date")
        
        if st.button("Search Accommodations"):
            accommodations = db.search_accommodations(
                location, min_price, max_price, checkin_date, checkout_date
            )
            if accommodations:
                st.session_state.available_accommodations = accommodations
                st.session_state.booking_step = 'select'
                st.rerun()
            else:
                st.info("No accommodations found matching your criteria.")
    
    # Show selection form if we're in select step
    elif st.session_state.booking_step == 'select':
        if 'available_accommodations' in st.session_state:
            df = pd.DataFrame(st.session_state.available_accommodations)
            df['price'] = df['price'].apply(format_price)
            st.dataframe(df)
            
            accom_id = st.number_input("Enter Accommodation ID to book:", min_value=1)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Book Selected Accommodation"):
                    selected_accom = next(
                        (a for a in st.session_state.available_accommodations 
                         if a['accommodationId'] == accom_id), None
                    )
                    
                    if selected_accom:
                        price = float(str(selected_accom['price']).replace('₹', '').replace(',', ''))
                        
                        if db.create_booking('accommodation', st.session_state.user_id, 
                                          price, accommodation_id=accom_id):
                            booking_id = db.get_last_booking_id()
                            st.session_state.current_booking = {
                                'id': booking_id,
                                'price': price
                            }
                            st.session_state.show_payment = True
                            st.session_state.booking_step = 'payment'
                            st.rerun()
                        else:
                            st.error("Failed to create booking. Please try again.")
                    else:
                        st.error("Please select a valid accommodation from the search results.")
            
            with col2:
                if st.button("Back to Search"):
                    st.session_state.booking_step = 'search'
                    if 'available_accommodations' in st.session_state:
                        del st.session_state.available_accommodations
                    st.rerun()

def customer_page():
    st.title("Customer Dashboard")
    
    if st.button("Logout", key='customer_logout'):
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()

    # If payment is in progress, show only the payment form
    if st.session_state.show_payment:
        show_payment_form()
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        "Analytics", "Book Flight", "Book Accommodation", "Booking History"
    ])
    
    with tab1:
        show_customer_analytics()
    
    with tab2:
        advanced_flight_search()
    
    with tab3:
        advanced_accommodation_search()
    
    with tab4:
        show_booking_history()

def show_admin_analytics():
    st.subheader("Revenue Analytics")
    
    # Get overall stats
    stats = db.get_booking_stats()
    
    # Display metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Bookings", stats['total_bookings'])
    with col2:
        st.metric("Total Revenue", format_price(stats['total_revenue']))
    with col3:
        st.metric("Average Booking Value", format_price(stats['avg_booking_value']))
    
    # Monthly stats
    monthly_stats = db.get_monthly_stats()
    if monthly_stats:
        df_monthly = pd.DataFrame(monthly_stats, columns=['month', 'total_bookings', 'total_revenue', 'avg_booking_value'])
        df_monthly['month'] = pd.to_datetime(df_monthly['month'], format='%Y-%m')
        df_monthly = df_monthly.sort_values(by='month')
        
        # Revenue trend
        fig_revenue = px.line(
            df_monthly,
            x='month',
            y='total_revenue',
            title='Monthly Revenue Trend'
        )
        st.plotly_chart(fig_revenue)
        
        # Bookings trend
        fig_bookings = px.bar(
            df_monthly,
            x='month',
            y='total_bookings',
            title='Monthly Bookings Trend'
        )
        st.plotly_chart(fig_bookings)
    else:
        st.write("No booking data available yet.")
    
    # Popular destinations
    st.subheader("Popular Destinations")
    destinations = db.get_popular_destinations()
    if destinations:
        df_dest = pd.DataFrame(destinations)
        fig_dest = px.pie(
            df_dest,
            values='total_bookings',
            names='destination',
            title='Bookings by Destination'
        )
        st.plotly_chart(fig_dest)

def admin_page():
    st.title("Admin Dashboard")
    
    if st.button("Logout", key='admin_logout'):
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()
    
    tab1, tab2, tab3 = st.tabs(["Analytics", "Bookings", "Payments"])
    
    with tab1:
        show_admin_analytics()

        # New section to show user revenue analysis
        st.subheader("User Revenue Analysis")
        user_revenue_data = db.get_admin_user_revenue_analysis()
        if user_revenue_data:
            df = pd.DataFrame(user_revenue_data)
            st.dataframe(df)
    
    with tab2:
        st.subheader("Bookings Management")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("View All Bookings"):
                st.session_state.filtered_bookings = db.get_all_bookings()
        with col2:
            if st.button("View Flight Bookings"):
                st.session_state.filtered_bookings = db.get_bookings_by_type('flight')
        with col3:
            if st.button("View Accommodation Bookings"):
                st.session_state.filtered_bookings = db.get_bookings_by_type('accommodation')
        
        if 'filtered_bookings' in st.session_state and st.session_state.filtered_bookings:
            bookings_df = pd.DataFrame(st.session_state.filtered_bookings)
            if st.button("Sort by Price"):
                bookings_df = bookings_df.sort_values('price', ascending=False)
            st.dataframe(bookings_df)
            
            # Delete booking
            booking_to_delete = st.number_input("Enter Booking ID to delete:", min_value=1)
            if st.button("Delete Booking"):
                if db.delete_booking(booking_to_delete):
                    st.success(f"Booking {booking_to_delete} deleted successfully!")
                    st.session_state.filtered_bookings = db.get_all_bookings()
                    st.rerun()
                else:
                    st.error("Failed to delete booking!")
    
    with tab3:
        st.subheader("Payment Records")
        payments = db.get_all_payments()
        if payments:
            df_payments = pd.DataFrame(payments)
            df_payments['price'] = df_payments['price'].apply(format_price)
            st.dataframe(df_payments)

def show_payment_form():
    st.subheader("Payment Details")
    bank_name = st.text_input("Bank Name")
    payment_type = st.selectbox("Payment Type", ["Credit Card", "Debit Card", "Net Banking"])
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Process Payment"):
            if db.create_payment(payment_type, bank_name, st.session_state.user_id,
                               st.session_state.current_booking['id'],
                               st.session_state.current_booking['price']):
                st.success("Payment processed successfully!")
                st.session_state.payment_success = True
                
                # Get and display the payment record
                payments = db.get_all_payments()
                latest_payment = next((p for p in payments if p['bookingId'] == st.session_state.current_booking['id']), None)
                if latest_payment:
                    st.subheader("Payment Receipt")
                    st.write("Payment ID:", latest_payment['paymentId'])
                    st.write("Amount:", format_price(latest_payment['price']))
                    st.write("Bank:", latest_payment['bankName'])
                    st.write("Payment Type:", latest_payment['typeOfPayment'])
                    st.write("Date:", latest_payment['datetime'])
                
                if st.button("Book Another"):
                    st.session_state.show_payment = False
                    st.session_state.payment_success = False
                    st.session_state.booking_step = 'search'
                    if 'current_booking' in st.session_state:
                        del st.session_state.current_booking
                    st.rerun()
            else:
                st.error("Payment processing failed!")
    
    with col2:
        if st.button("Cancel Payment"):
            st.session_state.show_payment = False
            st.session_state.booking_step = 'search'
            if 'current_booking' in st.session_state:
                del st.session_state.current_booking
            st.rerun()

def main():
    if not st.session_state.logged_in:
        login_signup_page()
    else:
        if st.session_state.role == 'customer':
            customer_page()
        else:  # admin
            admin_page()

if __name__ == "__main__":
    main()
