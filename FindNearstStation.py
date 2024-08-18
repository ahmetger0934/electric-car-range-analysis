import requests
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Function to get charging stations using Google Places API
def get_charging_stations(api_key, location, radius=50000):
    if not isinstance(location, (list, tuple)) or len(location) != 2 or not all(isinstance(i, float) for i in location):
        raise ValueError("Location must be a list or tuple with exactly two float elements: latitude and longitude.")

    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

    keywords = ["electric vehicle charging station", "EV charging", "charging station", "elektrikli şarj istasyonu", "şarj istasyonu", "elektrikli araç şarj istasyonu"]

    stations = []

    for keyword in keywords:
        params = {
            "location": f"{location[0]},{location[1]}",
            "radius": radius,
            "keyword": keyword,
            "key": api_key
        }
        response = requests.get(url, params=params)
        if response.status_code != 200:
            print(f"Failed to retrieve charging stations for keyword: {keyword}.")
            continue

        places = response.json()
        if places['status'] != 'OK':
            print(f"Error in Places API with keyword: {keyword}: {places['status']}")
            continue

        for place in places['results']:
            lat = place['geometry']['location']['lat']
            lng = place['geometry']['location']['lng']
            name = place['name']
            station = {"name": name, "location": (lat, lng)}

            # Avoid duplicates by checking station names
            if not any(s['name'] == station['name'] for s in stations):
                stations.append(station)

    return stations

# Function to get directions between locations using Google Directions API
def get_directions(api_key, origin, destination):
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": f"{origin[0]},{origin[1]}",
        "destination": f"{destination[0]},{destination[1]}",
        "key": api_key,
        "mode": "driving"
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print("Failed to retrieve directions.")
        return None

    directions = response.json()
    if directions['status'] != 'OK':
        print(f"Error in Directions API: {directions['status']}")
        return None

    distance_value = directions['routes'][0]['legs'][0]['distance']['value']

    return distance_value / 1000  # Convert meters to kilometers

# Function to add edges between the vehicle and stations
def add_vehicle_edges(G, vehicle_node, stations, api_key):
    for i, station in enumerate(stations):
        distance = get_directions(api_key, G.nodes[vehicle_node]['pos'], station['location'])
        if distance:
            G.add_edge(vehicle_node, i, weight=distance)
            print(f"Edge added between vehicle and station {station['name']} with distance {distance} km.")

# Function to update the plot in real-time
def update_plot(frame, G, ax, pos, paths_explored, shortest_path, vehicle_node, nearest_station_node):
    ax.clear()

    # Draw all nodes
    node_colors = ['red'] * (len(G.nodes) - 1)
    node_colors.insert(vehicle_node, 'blue')  # Vehicle is blue

    if frame == len(paths_explored):  # At the end, change nearest station to green
        node_colors[nearest_station_node] = 'green'

    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, node_size=700)

    # Draw all edges with low opacity
    nx.draw_networkx_edges(G, pos, edgelist=G.edges(), ax=ax, alpha=0.3)

    # Highlight the paths explored up to the current frame
    if frame < len(paths_explored):
        path_edges = paths_explored[frame]
        nx.draw_networkx_edges(G, pos, edgelist=path_edges, ax=ax, edge_color='black', width=2)

    # Highlight the final shortest path at the end
    if frame == len(paths_explored):
        nx.draw_networkx_edges(G, pos, edgelist=shortest_path, ax=ax, edge_color='red', width=2)

    # Draw node labels with improved visibility
    labels = nx.get_node_attributes(G, 'name')
    nx.draw_networkx_labels(G, pos, labels, ax=ax, font_size=10, bbox=dict(facecolor='white', edgecolor='none', alpha=0.8))

    ax.set_title("Real-Time Graph Simulation: Evaluating Paths to Nearest Station")

# Main function to execute the simulation
def main():
    api_key = "YOUR_GOOGLE_MAPS_API_KEY"
    vehicle_location = (39.343329, 28.180532)  # Example vehicle location

    stations = get_charging_stations(api_key, vehicle_location)
    if not stations:
        print("No charging stations found.")
        return

    G = nx.Graph()

    # Add stations as nodes
    for i, station in enumerate(stations):
        G.add_node(i, pos=station['location'], name=station['name'])

    # Add the vehicle as a node
    vehicle_node = len(G.nodes)
    G.add_node(vehicle_node, pos=vehicle_location, name="Vehicle")

    # Add edges between the vehicle and stations
    add_vehicle_edges(G, vehicle_node, stations, api_key)

    # Explore all paths and find the shortest one
    paths_explored = []
    shortest_distance = float('inf')
    shortest_path = None
    nearest_station_node = None

    for station_node in range(len(stations)):
        try:
            path = nx.shortest_path(G, source=vehicle_node, target=station_node, weight='weight')
            path_edges = list(zip(path[:-1], path[1:]))
            paths_explored.append(path_edges)

            # Check if this is the shortest path
            path_length = sum(nx.shortest_path_length(G, source=edge[0], target=edge[1], weight='weight') for edge in path_edges)
            if path_length < shortest_distance:
                shortest_distance = path_length
                shortest_path = path_edges
                nearest_station_node = station_node
        except nx.NetworkXNoPath:
            continue

    # Output the nearest station's name
    if nearest_station_node is not None:
        nearest_station_name = G.nodes[nearest_station_node]['name']
        print(f"The nearest charging station is: {nearest_station_name}")

    # Use spring layout for better spacing between nodes
    pos = nx.spring_layout(G, k=1, seed=42)

    fig, ax = plt.subplots(figsize=(10, 8))

    ani = FuncAnimation(fig, update_plot, frames=len(paths_explored) + 1, fargs=(G, ax, pos, paths_explored, shortest_path, vehicle_node, nearest_station_node),
                        interval=1000, repeat=False)

    plt.show()

if __name__ == "__main__":
    main()