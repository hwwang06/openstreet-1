from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import json

async def main():
    # Configure connection to the OSM MCP server
    server_params = StdioServerParameters(
        command="osm-mcp-server",
        args=[],
        env=None
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()
            
            # Get information about tools
            response = await session.list_tools()
            tools = response.tools
            print(f"Available tools: {[tool.name for tool in tools]}")
            
            # Example 1: Geocode a location (using a tool)
            print("\n--- Example 1: Geocode a Location ---")

            location_result = await session.call_tool(
                "geocode_address", 
                {"address": "San Francisco"}
            )
            
            # Parse the JSON response from the text content
            locations = []
            for content_item in location_result.content:
                if content_item.type == 'text':
                    locations.append(json.loads(content_item.text))
            
            if locations and len(locations) > 0:
                print(f"Found place: {locations[0].get('display_name', 'Unknown')}")
                lat = float(locations[0].get('lat', 0))
                lon = float(locations[0].get('lon', 0))
                print(f"Coordinates: {lat}, {lon}")

if __name__ == "__main__":
    asyncio.run(main())
