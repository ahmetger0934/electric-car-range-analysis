import requests
import folium
import numpy as np
from scipy import stats


# Calculate mean and standard deviation based on recorded data for 5% charge
def calculate_statistics(data):
    mean = np.mean(data)
    std_dev = np.std(data)
    return mean, std_dev


# Perform hypothesis testing on the vehicle range
def hypothesis_test(data, hypothesized_mean):
    mean, std_dev = calculate_statistics(data)
    t_statistic, p_value = stats.ttest_1samp(data, hypothesized_mean)
    return mean, std_dev, t_statistic, p_value


# Calculate the maximum distance the vehicle can travel with the remaining charge
def calculate_max_distance(Q, mean):
    return (Q * 1000) / mean


# Fetch nearby electric vehicle (EV) charging stations using Google Places API
def get_charging_stations(api_key, location, radius=500000):
    if not isinstance(location, (list, tuple)) or len(location) != 2 or not all(isinstance(i, float) for i in location):
        raise ValueError("Location must be a list or tuple with exactly two float elements: latitude and longitude.")

    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

    keywords = ["electric vehicle charging station", "EV charging", "charging station", "elektrikli şarj istasyonu",
                " şarj istasyonu", "elektrikli araç şarj istasyonu"]

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

            # Avoid duplicates
            if station not in stations:
                stations.append(station)

    return stations


# Fetch driving directions and route using Google Maps Directions API
def get_directions(api_key, origin, destination):
    if not isinstance(origin, (list, tuple)) or len(origin) != 2 or not all(isinstance(i, float) for i in origin):
        raise ValueError("Origin must be a list or tuple with exactly two float elements: latitude and longitude.")

    if not isinstance(destination, (list, tuple)) or len(destination) != 2 or not all(
            isinstance(i, float) for i in destination):
        raise ValueError("Destination must be a list or tuple with exactly two float elements: latitude and longitude.")

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
        return None, None
    directions = response.json()
    if directions['status'] != 'OK':
        print(f"Error in Directions API: {directions['status']}")
        return None, None

    distance_value = directions['routes'][0]['legs'][0]['distance']['value']
    polyline_points = directions['routes'][0]['overview_polyline']['points']

    return distance_value / 1000, polyline_points  # Convert meters to kilometers


# Find the nearest charging station based on driving distance
def find_nearest_station(api_key, vehicle_location, charging_stations):
    min_distance = float('inf')
    nearest_station = None
    best_route_polyline = None

    for station in charging_stations:
        distance_value, polyline_points = get_directions(api_key, vehicle_location, station['location'])
        if distance_value is None:
            continue
        if distance_value < min_distance:
            min_distance = distance_value
            nearest_station = station
            best_route_polyline = polyline_points

    return nearest_station, min_distance, best_route_polyline


# Create a map and plot vehicle and station locations with the route
def create_map_with_route(vehicle_location, charging_stations, nearest_station, polyline_points, remaining_km):
    vehicle_lat, vehicle_lng = vehicle_location
    m = folium.Map(location=[vehicle_lat, vehicle_lng], zoom_start=12)

    # Add marker for vehicle location
    folium.Marker(
        location=[vehicle_lat, vehicle_lng],
        popup=f"Vehicle Location (Remaining KM: {remaining_km:.2f} km)",
        icon=folium.Icon(color='blue')
    ).add_to(m)

    # Add markers for charging stations
    for station in charging_stations:
        station_location = station['location']
        station_name = station['name']
        folium.Marker(
            location=station_location,
            popup=f"{station_name}",
            icon=folium.Icon(color='green' if station_location == nearest_station['location'] else 'red')
        ).add_to(m)

    # Draw route line from vehicle to nearest station
    if polyline_points:
        decoded_route = decode_polyline(polyline_points)
        folium.PolyLine(locations=decoded_route, color="blue").add_to(m)

    # Save the map as an HTML file
    m.save('vehicle_charging_map_with_route.html')


# Decode polyline into lat/lon coordinates
def decode_polyline(polyline_str):
    index, lat, lng, coordinates = 0, 0, 0, []
    changes = {'latitude': [], 'longitude': []}

    while index < len(polyline_str):
        for unit in ['latitude', 'longitude']:
            shift, result = 0, 0

            while True:
                byte = ord(polyline_str[index]) - 63
                index += 1
                result |= (byte & 0x1f) << shift
                shift += 5
                if byte < 0x20:
                    break

            if (result & 1):
                changes[unit].append(~(result >> 1))
            else:
                changes[unit].append(result >> 1)

        lat += changes['latitude'][-1]
        lng += changes['longitude'][-1]
        coordinates.append((lat / 100000.0, lng / 100000.0))

    return coordinates


# Adjust the vehicle's performance to extend range
def adjust_performance(Q, mean, D_station, performance_factor):
    D_max = calculate_max_distance(Q, mean)

    if D_station > D_max:
        mean_adjusted = mean * (1 - performance_factor)
        D_max_adjusted = calculate_max_distance(Q, mean_adjusted)

        while D_max_adjusted < D_station:
            performance_factor += 0.05
            mean_adjusted = mean * (1 - performance_factor)
            D_max_adjusted = calculate_max_distance(Q, mean_adjusted)

        return mean_adjusted, D_max_adjusted

    return mean, D_max


# Main Function to Execute
def main():
    api_key = "YOUR_GOOGLE_MAPS_API_KEY" # Replace with your Google Maps API key

    # Example vehicle location (latitude, longitude) - should be set correctly
    vehicle_location = (39.343329, 28.180532)  # Example: Istanbul, Turkey

    # Ensure the vehicle location is valid
    if not isinstance(vehicle_location, (list, tuple)) or len(vehicle_location) != 2 or not all(
            isinstance(i, float) for i in vehicle_location):
        raise ValueError(
            "Vehicle location must be a list or tuple with exactly two float elements: latitude and longitude.")

    # Step 1: Find all charging stations within a certain radius
    charging_stations = get_charging_stations(api_key, vehicle_location)
    if not charging_stations:
        print("No charging stations found.")
        return
    print(f"Found {len(charging_stations)} charging stations nearby.")

    # Step 2: Find the nearest charging station
    nearest_station, D_station, best_route_polyline = find_nearest_station(api_key, vehicle_location, charging_stations)
    if nearest_station is None:
        print("Failed to find a route to any charging station.")
        return

    print(f"Nearest charging station is at {nearest_station['name']} with a driving distance of {D_station:.2f} km.")

    # Step 3: Perform hypothesis testing on the vehicle range with 5% battery
    sample_data = [20.5, 18.9, 23.2, 21.5, 19.0, 22.4, 24.1, 20.9, 21.3, 20.6]
    sample_data_km = [x * 1.60934 for x in sample_data]  # Convert miles to kilometers
    hypothesized_mean = 21 * 1.60934  # Hypothetical mean range with 5% charge in km
    mean, std_dev, t_statistic, p_value = hypothesis_test(sample_data_km, hypothesized_mean)

    print(
        f"Hypothesis Test Results: Mean = {mean:.2f} km, Std Dev = {std_dev:.2f} km, T-statistic = {t_statistic:.2f}, P-value = {p_value:.4f}")

    # Step 4: Calculate the vehicle's range based on remaining charge and statistical mean
    Q = 1.25  # kWh remaining (5% charge corresponding to 1.25 kWh in this scenario)
    initial_D_max = calculate_max_distance(Q, mean)
    print(f"Initial Vehicle's Maximum Range (D_max): {initial_D_max:.2f} km")

    # Step 5: Compare the maximum range (D_max) with the distance to the nearest station
    can_reach_with_D_max = D_station <= initial_D_max

    if can_reach_with_D_max:
        print(f"Car can reach the charging station with the maximum expected range of {initial_D_max:.2f} km.")
    else:
        print(
            f"Warning: The distance to the charging station ({D_station:.2f} km) exceeds the vehicle's maximum range ({initial_D_max:.2f} km).")
        print("Recommend reducing performance to extend the vehicle's range.")

        # Reduce performance and calculate the new maximum range
        performance_factor = 0.1
        mean_adjusted, adjusted_D_max = adjust_performance(Q, mean, D_station, performance_factor)
        print(
            f"After reducing performance, the vehicle's maximum range (D_max) is adjusted to: {adjusted_D_max:.2f} km.")

        if adjusted_D_max >= D_station:
            print(
                f"After reducing performance, the vehicle can now reach the nearest charging station with a new range of {adjusted_D_max:.2f} km.")
        else:
            print(
                "Even after reducing performance, the vehicle may not reach the nearest charging station. Please plan accordingly.")
    # Step 6: Create a map and show the route to the nearest station
    create_map_with_route(vehicle_location, charging_stations, nearest_station, best_route_polyline, initial_D_max)
    print("Map with route and remaining range has been saved as 'vehicle_charging_map_with_route.html'.")


if __name__ == "__main__":
    main()