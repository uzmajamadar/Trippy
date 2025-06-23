from flask import Flask, render_template, request, jsonify, session
from datetime import datetime, timedelta
import os
import json
import google.generativeai as genai
from serpapi import GoogleSearch
import requests
from werkzeug.security import generate_password_hash
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import configuration
from config import config

app = Flask(__name__)

# Load configuration
config_name = os.getenv('FLASK_ENV', 'default')
app.config.from_object(config[config_name])

# Configure Gemini AI
GEMINI_API_KEY = app.config['GEMINI_API_KEY']
SERP_API_KEY = app.config['SERP_API_KEY']

if not GEMINI_API_KEY or GEMINI_API_KEY == 'your-gemini-api-key':
    print("⚠️  Warning: GEMINI_API_KEY not configured!")

if not SERP_API_KEY or SERP_API_KEY == 'your-serp-api-key':
    print("⚠️  Warning: SERP_API_KEY not configured!")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(app.config['GEMINI_MODEL'])

class TravelAgent:
    def __init__(self):
        self.conversation_history = []
    
    def search_flights(self, origin, destination, departure_date, return_date=None, passengers=1, budget=None):
        """Search for flights using SERP API"""
        try:
            # Convert city names to airport codes if needed
            origin_code = self.get_airport_code(origin)
            destination_code = self.get_airport_code(destination)
            
            params = {
                "engine": "google_flights",
                "departure_id": origin_code,
                "arrival_id": destination_code,
                "outbound_date": departure_date,
                "currency": "USD",
                "adults": passengers,
                "api_key": SERP_API_KEY
            }
            
            if return_date:
                params["return_date"] = return_date
                params["type"] = "2"  # Round trip
            else:
                params["type"] = "1"  # One way
            
            search = GoogleSearch(params)
            results = search.get_dict()
            
            # Debug: Print the results to see what we're getting
            print(f"Flight search results keys: {results.keys()}")
            
            flights = []
            
            # Try different result keys that Google Flights might use
            flight_results = None
            if "best_flights" in results:
                flight_results = results["best_flights"]
            elif "other_flights" in results:
                flight_results = results["other_flights"]
            elif "flights" in results:
                flight_results = results["flights"]
            
            if flight_results:
                for flight in flight_results[:app.config['MAX_FLIGHTS_RESULTS']]:
                    # Get price and convert to float
                    price_raw = flight.get("price", 0)
                    try:
                        price = float(str(price_raw).replace('$', '').replace(',', '')) if price_raw else 0
                    except (ValueError, TypeError):
                        price = 0
                    
                    # Get flight details with fallbacks
                    flight_legs = flight.get("flights", [{}])
                    first_leg = flight_legs[0] if flight_legs else {}
                    
                    flight_info = {
                        "airline": first_leg.get("airline", "Unknown"),
                        "price": price,
                        "duration": flight.get("total_duration", "Unknown"),
                        "departure_time": first_leg.get("departure_airport", {}).get("time", "Unknown"),
                        "arrival_time": first_leg.get("arrival_airport", {}).get("time", "Unknown"),
                        "stops": len(flight_legs) - 1 if flight_legs else 0
                    }
                    
                    if budget is None or flight_info["price"] <= budget:
                        flights.append(flight_info)
            
            # If no flights found, create some sample data for demonstration
            if not flights:
                flights = self.create_sample_flights(origin, destination, budget)
            
            return flights
        except Exception as e:
            print(f"Flight search error: {e}")
            # Return sample flights if API fails
            return self.create_sample_flights(origin, destination, budget)
    
    def get_airport_code(self, city):
        """Convert city names to airport codes"""
        city_to_airport = {
            "new york": "JFK",
            "nyc": "JFK",
            "los angeles": "LAX",
            "la": "LAX",
            "chicago": "ORD",
            "miami": "MIA",
            "san francisco": "SFO",
            "boston": "BOS",
            "washington": "DCA",
            "seattle": "SEA",
            "denver": "DEN",
            "atlanta": "ATL",
            "dallas": "DFW",
            "houston": "IAH",
            "phoenix": "PHX",
            "las vegas": "LAS",
            "orlando": "MCO",
            "detroit": "DTW",
            "minneapolis": "MSP",
            "philadelphia": "PHL",
            "london": "LHR",
            "paris": "CDG",
            "tokyo": "NRT",
            "sydney": "SYD",
            "toronto": "YYZ",
            "vancouver": "YVR",
            "amsterdam": "AMS",
            "frankfurt": "FRA",
            "rome": "FCO",
            "madrid": "MAD",
            "barcelona": "BCN",
            "dubai": "DXB",
            "singapore": "SIN",
            "hong kong": "HKG",
            "mumbai": "BOM",
            "delhi": "DEL",
            "bangkok": "BKK",
            "istanbul": "IST"
        }
        
        city_lower = city.lower().strip()
        return city_to_airport.get(city_lower, city.upper())
    
    def create_sample_flights(self, origin, destination, budget=None):
        """Create sample flight data for demonstration"""
        import random
        
        airlines = ["American Airlines", "Delta", "United", "JetBlue", "Southwest", "Emirates", "Lufthansa"]
        
        # Generate realistic prices based on route
        base_price = 300
        if any(city in destination.lower() for city in ["paris", "london", "tokyo", "sydney"]):
            base_price = 800  # International flights
        
        flights = []
        for i in range(3):
            price = base_price + random.randint(-100, 300)
            if budget and price > budget:
                price = int(budget * 0.8)  # Make it within budget
            
            flight = {
                "airline": random.choice(airlines),
                "price": price,
                "duration": f"{random.randint(2, 15)}h {random.randint(0, 59)}m",
                "departure_time": f"{random.randint(6, 22):02d}:{random.randint(0, 59):02d}",
                "arrival_time": f"{random.randint(6, 22):02d}:{random.randint(0, 59):02d}",
                "stops": random.choice([0, 0, 1, 2])  # Mostly direct flights
            }
            flights.append(flight)
        
        return flights
    
    def search_hotels(self, destination, check_in, check_out, guests=1, budget=None):
        """Search for hotels using SERP API"""
        try:
            params = {
                "engine": "google_hotels",
                "q": f"hotels in {destination}",
                "check_in_date": check_in,
                "check_out_date": check_out,
                "adults": guests,
                "currency": "USD",
                "api_key": SERP_API_KEY
            }
            
            search = GoogleSearch(params)
            results = search.get_dict()
            
            # Debug: Print the results to see what we're getting
            print(f"Hotel search results keys: {results.keys()}")
            
            hotels = []
            if "properties" in results:
                for hotel in results["properties"][:app.config['MAX_HOTELS_RESULTS']]:
                    # Get price and convert to float
                    price_raw = hotel.get("rate_per_night", {}).get("lowest", 0)
                    try:
                        price = float(str(price_raw).replace('$', '').replace(',', '')) if price_raw else 0
                    except (ValueError, TypeError):
                        price = 0
                    hotel_name = hotel.get("name", "Unknown Hotel")
                    hotel_location = hotel.get("neighborhood", "")
                    
                    hotel_info = {
                        "name": hotel_name,
                        "price": price,
                        "rating": hotel.get("overall_rating", 0),
                        "reviews": hotel.get("reviews", 0),
                        "amenities": hotel.get("amenities", []),
                        "location": hotel_location,
                        "image": hotel.get("images", [{}])[0].get("thumbnail", ""),
                        "maps_link": self.get_google_maps_link(destination, hotel_name)
                    }
                    
                    if budget is None or hotel_info["price"] <= budget:
                        hotels.append(hotel_info)
            
            # If no hotels found, create sample data
            if not hotels:
                hotels = self.create_sample_hotels(destination, budget)
            
            return hotels
        except Exception as e:
            print(f"Hotel search error: {e}")
            # Return sample hotels if API fails
            return self.create_sample_hotels(destination, budget)
    
    def create_sample_hotels(self, destination, budget=None):
        """Create sample hotel data for demonstration"""
        import random
        
        hotel_chains = [
            "Marriott", "Hilton", "Hyatt", "InterContinental", "Sheraton",
            "Holiday Inn", "Best Western", "Radisson", "Westin", "Renaissance"
        ]
        
        amenities_list = [
            ["Free WiFi", "Pool", "Gym"],
            ["Free WiFi", "Spa", "Restaurant"],
            ["Free WiFi", "Business Center", "Parking"],
            ["Pool", "Gym", "Room Service"],
            ["Spa", "Restaurant", "Bar"],
            ["Free WiFi", "Pool", "Pet Friendly"]
        ]
          # Generate realistic prices based on destination
        base_price = 120
        if any(city in destination.lower() for city in ["paris", "london", "tokyo", "new york"]):
            base_price = 200  # Expensive cities
        
        hotels = []
        for i in range(6):
            price = base_price + random.randint(-50, 150)
            if budget and price > budget:
                price = int(budget * 0.7)  # Make it within budget
            
            hotel_name = f"{random.choice(hotel_chains)} {destination}"
            hotel_location = f"{destination} City Center"
            
            hotel = {
                "name": hotel_name,
                "price": price,
                "rating": round(random.uniform(3.5, 4.8), 1),
                "reviews": random.randint(100, 2000),
                "amenities": random.choice(amenities_list),
                "location": hotel_location,
                "image": "",
                "maps_link": self.get_google_maps_link(destination, hotel_name)
            }
            hotels.append(hotel)
        
        return hotels
    
    def generate_itinerary(self, destination, dates, interests, people_count, budget):
        """Generate personalized itinerary using Gemini AI"""
        try:
            prompt = f"""
            Create a detailed travel itinerary for {people_count} people visiting {destination}.
            
            Travel Details:
            - Dates: {dates}
            - Interests: {interests}
            - Budget: ${budget} total
            - Group size: {people_count} people
            
            Please provide a day-by-day itinerary with:
            1. Daily activities and attractions based on interests
            2. Recommended restaurants for different meal times
            3. Transportation suggestions within the city
            4. Budget breakdown for activities
            5. Local tips and cultural insights
            6. Emergency contacts and important information
            
            Format the response as a clean, structured plan without using # symbols or markdown formatting.
            Use clear headings and organize information in a readable format.
            """
            
            response = model.generate_content(prompt)
            # Convert the response to HTML format
            return self.format_itinerary_html(response.text, destination, people_count)
        except Exception as e:
            print(f"Itinerary generation error: {e}")
            return self.create_sample_itinerary(destination, dates, interests, people_count, budget)
    
    def format_itinerary_html(self, text, destination, people_count):
        """Convert plain text itinerary to beautiful HTML"""
        import re
        
        # Remove excessive markdown symbols
        text = re.sub(r'#{1,6}\s*', '', text)
        text = re.sub(r'\*{2,}', '', text)
        text = re.sub(r'_{2,}', '', text)
        
        # Split into sections
        lines = text.split('\n')
        html_content = []
        
        current_day = None
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Detect day headers
            if re.match(r'day\s*\d+', line.lower()) or re.match(r'\d+\.\s*day', line.lower()):
                if current_day:
                    html_content.append('</div>')
                current_day = line
                html_content.append(f'''
                <div class="itinerary-day">
                    <div class="day-header">
                        <i class="fas fa-calendar-day"></i>
                        <h3>{line}</h3>
                    </div>
                    <div class="day-content">
                ''')
            
            # Detect time-based activities
            elif re.match(r'\d{1,2}:\d{2}|\d{1,2}\s*(am|pm)', line.lower()):
                html_content.append(f'''
                    <div class="activity-time">
                        <i class="fas fa-clock"></i>
                        <span class="time">{line}</span>
                    </div>
                ''')
            
            # Detect section headers
            elif any(keyword in line.lower() for keyword in ['morning', 'afternoon', 'evening', 'breakfast', 'lunch', 'dinner', 'transportation', 'tips', 'budget']):
                html_content.append(f'''
                    <div class="section-header">
                        <i class="fas fa-star"></i>
                        <h4>{line}</h4>
                    </div>
                ''')
            
            # Regular content
            else:
                if line.startswith('-') or line.startswith('•'):
                    line = line[1:].strip()
                    html_content.append(f'<div class="activity-item"><i class="fas fa-map-marker-alt"></i> {line}</div>')
                else:
                    html_content.append(f'<p class="itinerary-text">{line}</p>')
        
        if current_day:
            html_content.append('</div></div>')
        
        return ''.join(html_content)
    
    def create_sample_itinerary(self, destination, dates, interests, people_count, budget):
        """Create a sample itinerary with beautiful formatting"""
        return f'''
        <div class="itinerary-day">
            <div class="day-header">
                <i class="fas fa-calendar-day"></i>
                <h3>Day 1: Arrival in {destination}</h3>
            </div>
            <div class="day-content">
                <div class="section-header">
                    <i class="fas fa-sun"></i>
                    <h4>Morning</h4>
                </div>
                <div class="activity-time">
                    <i class="fas fa-clock"></i>
                    <span class="time">9:00 AM</span>
                </div>
                <div class="activity-item">
                    <i class="fas fa-plane"></i> Arrive at {destination} Airport
                </div>
                <div class="activity-item">
                    <i class="fas fa-taxi"></i> Transfer to hotel via taxi/rideshare ($25-40)
                </div>
                
                <div class="section-header">
                    <i class="fas fa-sun"></i>
                    <h4>Afternoon</h4>
                </div>
                <div class="activity-time">
                    <i class="fas fa-clock"></i>
                    <span class="time">2:00 PM</span>
                </div>
                <div class="activity-item">
                    <i class="fas fa-utensils"></i> Lunch at local restaurant ($15-25 per person)
                </div>
                <div class="activity-item">
                    <i class="fas fa-walking"></i> Walking tour of city center
                </div>
                
                <div class="section-header">
                    <i class="fas fa-moon"></i>
                    <h4>Evening</h4>
                </div>
                <div class="activity-time">
                    <i class="fas fa-clock"></i>
                    <span class="time">7:00 PM</span>
                </div>
                <div class="activity-item">
                    <i class="fas fa-utensils"></i> Dinner at recommended restaurant ($30-50 per person)
                </div>
            </div>
        </div>
        
        <div class="itinerary-day">
            <div class="day-header">
                <i class="fas fa-calendar-day"></i>
                <h3>Day 2: Exploring {destination}</h3>
            </div>
            <div class="day-content">
                <div class="section-header">
                    <i class="fas fa-sun"></i>
                    <h4>Full Day Adventure</h4>
                </div>
                <div class="activity-item">
                    <i class="fas fa-camera"></i> Visit top attractions based on your interests: {", ".join(interests[:3]) if interests else "sightseeing, culture, food"}
                </div>
                <div class="activity-item">
                    <i class="fas fa-subway"></i> Use public transportation ($5-10 per day)
                </div>
                <div class="activity-item">
                    <i class="fas fa-shopping-bag"></i> Shopping and souvenir hunting
                </div>
            </div>
        </div>
        
        <div class="budget-summary">
            <div class="section-header">
                <i class="fas fa-dollar-sign"></i>
                <h4>Budget Breakdown</h4>
            </div>
            <div class="budget-item">
                <i class="fas fa-utensils"></i> Meals: ${int(budget * 0.3) if budget else 200} ({people_count} people)
            </div>
            <div class="budget-item">
                <i class="fas fa-ticket-alt"></i> Activities: ${int(budget * 0.4) if budget else 300}
            </div>
            <div class="budget-item">
                <i class="fas fa-subway"></i> Transportation: ${int(budget * 0.2) if budget else 100}
            </div>
            <div class="budget-item">
                <i class="fas fa-shopping-bag"></i> Shopping: ${int(budget * 0.1) if budget else 50}
            </div>
        </div>
        
        <div class="travel-tips">
            <div class="section-header">
                <i class="fas fa-lightbulb"></i>
                <h4>Local Tips</h4>
            </div>
            <div class="tip-item">
                <i class="fas fa-info-circle"></i> Best time to visit attractions is early morning or late afternoon
            </div>
            <div class="tip-item">
                <i class="fas fa-credit-card"></i> Most places accept credit cards, but carry some cash
            </div>
            <div class="tip-item">
                <i class="fas fa-mobile-alt"></i> Download local transportation apps for easier navigation
            </div>        </div>
        '''
    def chat_response(self, user_message, context=None):
        """Generate chatbot responses using Gemini AI"""
        try:
            system_prompt = """
            You are a helpful AI travel assistant. You help users plan their trips, answer travel-related questions,
            and provide recommendations for destinations, activities, and travel tips. Be friendly, informative,
            and always consider the user's budget and preferences.
            
            Please provide clear, well-structured responses. Use bullet points for lists and organize information logically.
            Keep your responses concise but informative.
            """
            
            if context:
                prompt = f"{system_prompt}\n\nContext: {context}\n\nUser: {user_message}\n\nAssistant:"
            else:
                prompt = f"{system_prompt}\n\nUser: {user_message}\n\nAssistant:"
            
            response = model.generate_content(prompt)
            return self.format_chat_response(response.text)
        except Exception as e:
            print(f"Chat response error: {e}")
            return "I'm sorry, I'm having trouble responding right now. Please try again."
    
    def format_chat_response(self, text):
        """Format chat response to convert markdown to HTML"""
        import re
        
        # Convert markdown bold/italic to HTML
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
        
        # Convert markdown bullet points to HTML lists
        bullet_pattern = r'(\n\s*[-*]\s+.*?)+(?=\n\n|\n*$)'
        
        def replace_bullets(match):
            bullet_text = match.group(0)
            items = re.findall(r'\n\s*[-*]\s+(.*?)(?=\n\s*[-*]|\n*$)', bullet_text + '\n')
            html_list = '<ul>\n'
            for item in items:
                html_list += f'  <li>{item.strip()}</li>\n'
            html_list += '</ul>'
            return html_list
        
        text = re.sub(bullet_pattern, replace_bullets, '\n' + text)
        
        # Convert numbered lists to HTML
        numbered_pattern = r'(\n\s*\d+\.\s+.*?)+(?=\n\n|\n*$)'
        
        def replace_numbered(match):
            numbered_text = match.group(0)
            items = re.findall(r'\n\s*\d+\.\s+(.*?)(?=\n\s*\d+\.|\n*$)', numbered_text + '\n')
            html_list = '<ol>\n'
            for item in items:
                html_list += f'  <li>{item.strip()}</li>\n'
            html_list += '</ol>'
            return html_list
        
        text = re.sub(numbered_pattern, replace_numbered, '\n' + text)
        
        # Add paragraph tags for better formatting
        paragraphs = text.split('\n\n')
        formatted_paragraphs = []
        for p in paragraphs:
            if p.strip() and not (p.strip().startswith('<ul>') or p.strip().startswith('<ol>')):
                formatted_paragraphs.append(f'<p>{p.strip()}</p>')
            else:
                formatted_paragraphs.append(p.strip())
        
        return '\n'.join(formatted_paragraphs)
    
    def get_google_maps_link(self, location, hotel_name=None):
        """Generate a Google Maps link for a location"""
        query = f"{hotel_name}, {location}" if hotel_name else location
        # URL encode the query
        import urllib.parse
        encoded_query = urllib.parse.quote_plus(query)
        return f"https://www.google.com/maps/search/?api=1&query={encoded_query}"

travel_agent = TravelAgent()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search_travel():
    try:
        data = request.json
        
        # Extract search parameters
        origin = data.get('origin')
        destination = data.get('destination')
        departure_date = data.get('departure_date')
        return_date = data.get('return_date')
        check_in = data.get('check_in')
        check_out = data.get('check_out')
        people_count = int(data.get('people_count', 1))
        budget = float(data.get('budget', 0)) if data.get('budget') else None
        interests = data.get('interests', [])
        
        # Calculate budget allocation
        flight_budget = budget * app.config['FLIGHT_BUDGET_PERCENTAGE'] if budget else None
        hotel_budget = budget * app.config['HOTEL_BUDGET_PERCENTAGE'] if budget else None
        
        # Search flights and hotels
        flights = travel_agent.search_flights(origin, destination, departure_date, return_date, people_count, flight_budget)
        hotels = travel_agent.search_hotels(destination, check_in, check_out, people_count, hotel_budget)
        
        # Generate itinerary
        date_range = f"{departure_date} to {return_date if return_date else departure_date}"
        itinerary = travel_agent.generate_itinerary(destination, date_range, interests, people_count, budget)
        
        # Store in session for later use
        session['last_search'] = {
            'destination': destination,
            'dates': date_range,
            'people_count': people_count,
            'interests': interests,
            'budget': budget
        }
        
        return jsonify({
            'success': True,
            'flights': flights,
            'hotels': hotels,
            'itinerary': itinerary,
            'budget_breakdown': {
                'total': budget,
                'flights': flight_budget,
                'hotels': hotel_budget,
                'activities': budget * app.config['ACTIVITY_BUDGET_PERCENTAGE'] if budget else None
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message', '')
        
        # Get context from last search if available
        context = session.get('last_search')
        
        response = travel_agent.chat_response(user_message, context)
        
        return jsonify({
            'success': True,
            'response': response
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/suggestions')
def get_suggestions():
    """Get destination suggestions based on interests"""
    interests = request.args.get('interests', '').split(',')
    
    try:
        prompt = f"""
        Suggest 5 travel destinations that would be perfect for someone interested in: {', '.join(interests)}.
        For each destination, provide:
        1. Destination name
        2. Why it matches their interests
        3. Best time to visit
        4. Estimated budget range per person
        
        Format as JSON array.
        """
        
        response = model.generate_content(prompt)
        return jsonify({'suggestions': response.text})
    
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)