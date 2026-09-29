from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import json
from contextlib import AsyncExitStack
from datetime import datetime

class LocationAssistant:
    """A helper class that allows an LLM to interact with location services"""
    
    def __init__(self, server_command="osm-mcp-server", server_args=None):
        self.server_params = StdioServerParameters(
            command=server_command,
            args=server_args if server_args else [],
            env=None
        )
        self.session = None
        self.exit_stack = AsyncExitStack()
        
    async def __aenter__(self):
        """Setup the connection when entering the context manager"""
        # Use AsyncExitStack to properly manage resources
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(self.server_params))
        self.read, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.read, self.write))
        
        # Initialize the session
        await self.session.initialize()
        
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close the connection when exiting the context manager"""
        await self.exit_stack.aclose()
        
    def _parse_json_content(self, result):
        """Helper to parse JSON from TextContent"""
        if not result or not result.content:
            return None
            
        for content_item in result.content:
            if content_item.type == 'text':
                try:
                    return json.loads(content_item.text)
                except json.JSONDecodeError:
                    continue
        return None
        
    async def get_location_info(self, query):
        """Get information about a location from a text query"""
        result = await self.session.call_tool(
            "geocode_address", 
            {"address": query}
        )
        
        # Parse results
        results = []
        for content_item in result.content:
            if content_item.type == 'text':
                try:
                    location = json.loads(content_item.text)
                    results.append(location)
                except json.JSONDecodeError:
                    continue
        
        if results and len(results) > 0:
            return results[0]
        return None
    
    async def get_directions(self, from_place, to_place, mode="car", steps=False, overview="false", annotations=False):
        """Get directions between two places"""
        # Geocode both locations
        from_location = await self.get_location_info(from_place)
        to_location = await self.get_location_info(to_place)
        
        if not from_location or not to_location:
            return {"error": "Could not find one or both locations"}
        
        # Get directions
        if "coordinates" in from_location and "coordinates" in to_location:
            directions_result = await self.session.call_tool(
                "get_route_directions",
                {
                    "from_latitude": from_location["coordinates"]["latitude"],
                    "from_longitude": from_location["coordinates"]["longitude"],
                    "to_latitude": to_location["coordinates"]["latitude"],
                    "to_longitude": to_location["coordinates"]["longitude"],
                    "mode": mode,
                    "steps": steps,
                    "overview": overview,
                    "annotations": annotations
                }
            )
            
            directions = self._parse_json_content(directions_result)
            if not directions:
                return {"error": "Failed to parse directions result"}
            
            # Format the response in a way that's easy for an LLM to use
            formatted_directions = {
                "from": from_location["display_name"],
                "to": to_location["display_name"],
                "distance_km": round(directions["summary"]["distance"] / 1000, 2),
                "duration_minutes": round(directions["summary"]["duration"] / 60, 1),
                "steps": [step["instruction"] for step in directions["directions"]],
                "mode": mode
            }
            
            return formatted_directions
        
        return {"error": "No coordinates found for one or both locations"}
    
    # New method for finding schools
    async def find_schools(self, place, radius=2000, education_levels=None):
        """Find educational institutions near a location"""
        # First, geocode the place to get coordinates
        location = await self.get_location_info(place)
        if not location:
            return {"error": f"Could not find location: {place}"}
        
        # Now find schools
        if "coordinates" in location:
            schools_result = await self.session.call_tool(
                "find_schools_nearby",
                {
                    "latitude": location["coordinates"]["latitude"],
                    "longitude": location["coordinates"]["longitude"],
                    "radius": radius,
                    "education_levels": education_levels
                }
            )
            
            schools_info = self._parse_json_content(schools_result)
            if not schools_info:
                return {"error": "Failed to parse schools result"}
            
            # Add location context
            return {
                "location": location["display_name"],
                "coordinates": location["coordinates"],
                "schools": schools_info["schools"],
                "count": schools_info["count"]
            }
        
        return {"error": "No coordinates found for location"}
    
    # New method for commute analysis
    async def analyze_commute(self, home_location, work_location, modes=None):
        """Analyze commute options between home and work"""
        # Default modes if not specified
        if modes is None:
            modes = ["car", "bike", "foot"]
            
        # Geocode both locations
        home = await self.get_location_info(home_location)
        work = await self.get_location_info(work_location)
        
        if not home or not work:
            return {"error": "Could not find one or both locations"}
        
        # Get commute analysis
        if "coordinates" in home and "coordinates" in work:
            commute_result = await self.session.call_tool(
                "analyze_commute",
                {
                    "home_latitude": home["coordinates"]["latitude"],
                    "home_longitude": home["coordinates"]["longitude"],
                    "work_latitude": work["coordinates"]["latitude"],
                    "work_longitude": work["coordinates"]["longitude"],
                    "modes": modes
                }
            )
            
            commute_info = self._parse_json_content(commute_result)
            if not commute_info:
                return {"error": "Failed to parse commute analysis"}
                
            # Format for easier LLM use
            return {
                "home": home["display_name"],
                "work": work["display_name"],
                "options": commute_info["commute_options"],
                "fastest_option": commute_info["fastest_option"]
            }
        
        return {"error": "No coordinates found for one or both locations"}
    
    # New method for finding EV charging stations
    async def find_charging_stations(self, place, radius=5000, connector_types=None, min_power=None):
        """Find electric vehicle charging stations near a location"""
        # First, geocode the place to get coordinates
        location = await self.get_location_info(place)
        if not location:
            return {"error": f"Could not find location: {place}"}
        
        # Now find charging stations
        if "coordinates" in location:
            charging_result = await self.session.call_tool(
                "find_ev_charging_stations",
                {
                    "latitude": location["coordinates"]["latitude"],
                    "longitude": location["coordinates"]["longitude"],
                    "radius": radius,
                    "connector_types": connector_types,
                    "min_power": min_power
                }
            )
            
            charging_info = self._parse_json_content(charging_result)
            if not charging_info:
                return {"error": "Failed to parse charging stations result"}
            
            # Add location context
            return {
                "location": location["display_name"],
                "coordinates": location["coordinates"],
                "stations": charging_info["stations"],
                "count": charging_info["count"]
            }
        
        return {"error": "No coordinates found for location"}
    
    # New method for finding parking facilities
    async def find_parking(self, place, radius=1000, parking_type=None):
        """Find parking facilities near a location"""
        # First, geocode the place to get coordinates
        location = await self.get_location_info(place)
        if not location:
            return {"error": f"Could not find location: {place}"}
        
        # Now find parking
        if "coordinates" in location:
            parking_result = await self.session.call_tool(
                "find_parking_facilities",
                {
                    "latitude": location["coordinates"]["latitude"],
                    "longitude": location["coordinates"]["longitude"],
                    "radius": radius,
                    "parking_type": parking_type
                }
            )
            
            parking_info = self._parse_json_content(parking_result)
            if not parking_info:
                return {"error": "Failed to parse parking facilities result"}
            
            # Add location context
            return {
                "location": location["display_name"],
                "coordinates": location["coordinates"],
                "facilities": parking_info["parking_facilities"],
                "count": parking_info["count"]
            }
        
        return {"error": "No coordinates found for location"}


# Example usage of the Location Assistant by an LLM
async def example_llm_interaction():
    """
    This simulates how an LLM like Claude would use the Location Assistant
    to provide location-based services in a conversation.
    """
    async with LocationAssistant() as assistant:
        print("\n=== EXAMPLE 1: DIRECTIONS ===")
        print("User: 'How do I get from the Empire State Building to the Statue of Liberty?'")
        
        # Get directions
        directions = await assistant.get_directions(
            "Empire State Building", 
            "Statue of Liberty",
            "car"
        )
        
        if "error" not in directions:
            print("\nLLM response (using the data):")
            print(f"The distance from {directions['from']} to {directions['to']} is {directions['distance_km']} km.")
            print(f"By {directions['mode']}, it will take approximately {directions['duration_minutes']} minutes.")
            print("Here are the directions:")
            for i, step in enumerate(directions['steps'][:5], 1):
                print(f"  {i}. {step}")
            if len(directions['steps']) > 5:
                print(f"  ... plus {len(directions['steps']) - 5} more steps")
        else:
            print(f"Error: {directions['error']}")
            
        # New examples for real estate use cases
        print("\n=== EXAMPLE 2: SCHOOLS NEAR A HOME ===")
        print("User: 'What schools are near 123 Main St, Boston?'")
        
        # Find schools
        schools = await assistant.find_schools("123 Main St, Boston", radius=2000)
        
        if "error" not in schools:
            print("\nLLM response (using the data):")
            print(f"I found {schools['count']} educational institutions near {schools['location']}.")
            
            if schools['schools']:
                # Group by type
                school_types = {}
                for school in schools['schools'][:5]:
                    school_type = school.get('amenity_type', 'Unknown')
                    if school_type not in school_types:
                        school_types[school_type] = []
                    school_types[school_type].append(school)
                
                # Report by type
                for school_type, type_schools in school_types.items():
                    print(f"  {school_type.capitalize()} ({len(type_schools)}):")
                    for school in type_schools[:3]:
                        print(f"    • {school['name']} - {school['distance']/1000:.2f}km away")
        else:
            print(f"Error: {schools['error']}")
            
        print("\n=== EXAMPLE 3: COMMUTE ANALYSIS ===")
        print("User: 'What would my commute be like if I lived in Brooklyn and worked in Manhattan?'")
        
        # Analyze commute
        commute = await assistant.analyze_commute(
            "Brooklyn, NY",
            "Manhattan, NY",
            modes=["car", "bike", "foot"]
        )
        
        if "error" not in commute:
            print("\nLLM response (using the data):")
            print(f"Commuting from {commute['home']} to {commute['work']}:")
            
            for option in commute['options']:
                if "error" not in option:
                    print(f"  • By {option['mode']}: {option['distance_km']} km, approximately {option['duration_minutes']} minutes")
            
            fastest = commute.get('fastest_option')
            if fastest:
                print(f"\nThe fastest option is by {fastest}.")
        else:
            print(f"Error: {commute['error']}")
            
        # New examples for automotive use cases
        print("\n=== EXAMPLE 4: EV CHARGING STATIONS ===")
        print("User: 'Where can I charge my electric car near Seattle Center?'")
        
        # Find charging stations
        charging = await assistant.find_charging_stations("Seattle Center", radius=5000)
        
        if "error" not in charging:
            print("\nLLM response (using the data):")
            print(f"I found {charging['count']} EV charging stations near {charging['location']}.")
            
            if charging['stations']:
                print("Here are the closest options:")
                for i, station in enumerate(charging['stations'][:3], 1):
                    connectors = station.get('connectors', [])
                    connector_str = ", ".join([f"{c.get('type', 'standard')}" for c in connectors[:2]])
                    print(f"  {i}. {station['name']} - {station['distance']/1000:.2f}km away")
                    print(f"     Connectors: {connector_str if connector_str else 'Unknown'}")
                    print(f"     Operator: {station.get('operator', 'Unknown')}")
        else:
            print(f"Error: {charging['error']}")
            
        print("\n=== EXAMPLE 5: PARKING FACILITIES ===")
        print("User: 'Where can I park my car in downtown Chicago?'")
        
        # Find parking
        parking = await assistant.find_parking("Downtown Chicago", radius=1000)
        
        if "error" not in parking:
            print("\nLLM response (using the data):")
            print(f"I found {parking['count']} parking facilities in {parking['location']}.")
            
            if parking['facilities']:
                # Group by type
                parking_types = {}
                for facility in parking['facilities']:
                    p_type = facility.get('type', 'surface')
                    if p_type not in parking_types:
                        parking_types[p_type] = []
                    parking_types[p_type].append(facility)
                
                # Report by type
                for p_type, facilities in parking_types.items():
                    print(f"  {p_type.capitalize()} parking ({len(facilities)}):")
                    for facility in facilities[:2]:
                        fee = "Free" if facility.get('fee') == "no" else "Paid" if facility.get('fee') == "yes" else "Unknown fee"
                        print(f"    • {facility['name']} - {facility['distance']/1000:.2f}km away ({fee})")
        else:
            print(f"Error: {parking['error']}")


if __name__ == "__main__":
    asyncio.run(example_llm_interaction()) 
