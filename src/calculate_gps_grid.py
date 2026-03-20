import math
import pandas as pd

def calculate_new_coordinate(start_lat, start_lon, offset_north_ft, offset_east_ft):
    """Calculates a new GPS coordinate based on an offset in feet."""
    R_EARTH_FT = 20925721.78 

    # Change in Latitude (North/South)
    delta_lat = (offset_north_ft / R_EARTH_FT) * (180 / math.pi)

    # Change in Longitude (East/West)
    lat_radians = start_lat * (math.pi / 180)
    delta_lon = (offset_east_ft / (R_EARTH_FT * math.cos(lat_radians))) * (180 / math.pi)

    return start_lat + delta_lat, start_lon + delta_lon

# ==========================================
# 1. ANCHOR POINT
# ==========================================
# Corner of Porch at 252 E Utica St
ANCHOR_LAT = 42.9115083  # 42°54'41.43"N
ANCHOR_LON = -78.8563833 # 78°51'22.98"W

# ==========================================
# 2. EXACT GRID DIMENSIONS & OFFSETS
# ==========================================
# The "north_ft" and "east_ft" mark the EXACT CENTER of each rectangle.
grid_points = {
    # COLUMN 1 (7ft wide x 10ft long) - Center is 3.5 ft East
    "1A_Utica": {"north_ft": 5.0,  "east_ft": 3.5,  "width": 7, "length": 10},
    "1B_Utica": {"north_ft": 15.0, "east_ft": 3.5,  "width": 7, "length": 10},
    "1C_Utica": {"north_ft": 25.0, "east_ft": 3.5,  "width": 7, "length": 10},
    
    # COLUMN 2 (10ft wide x 10ft long) - Starts at 7 ft. Center is 12 ft East
    "2A_Utica": {"north_ft": 5.0,  "east_ft": 12.0, "width": 10, "length": 10},
    "2B_Utica": {"north_ft": 15.0, "east_ft": 12.0, "width": 10, "length": 10},
    "2C_Utica": {"north_ft": 25.0, "east_ft": 12.0, "width": 10, "length": 10},
    
    # COLUMN 3 (10ft wide x 10ft long) - Starts at 17 ft. Center is 22 ft East
    "3A_Utica": {"north_ft": 5.0,  "east_ft": 22.0, "width": 10, "length": 10},
    "3B_Utica": {"north_ft": 15.0, "east_ft": 22.0, "width": 10, "length": 10},
    "3C_Utica": {"north_ft": 25.0, "east_ft": 22.0, "width": 10, "length": 10},
    
    # EXTENSION 3D (10ft wide x 6ft long) - Starts at 30 ft North. Center is 33 ft North.
    "3D_Utica": {"north_ft": 33.0, "east_ft": 22.0, "width": 10, "length": 6},
}

# ==========================================
# 3. RUN CALCULATOR
# ==========================================
results = []
print("Calculating coordinates for 252 E Utica St...\n")

for sample_id, data in grid_points.items():
    new_lat, new_lon = calculate_new_coordinate(
        ANCHOR_LAT, 
        ANCHOR_LON, 
        data["north_ft"], 
        data["east_ft"]
    )
    
    results.append({
        "SampleID": sample_id,
        "Yard_Area": "Backyard",
        # We output a rough Grid_Size_ft average so your current dashboard still draws a box,
        # but we also save the true width and length if you want to upgrade the dashboard to draw rectangles later!
        "Grid_Size_ft": round((data["width"] + data["length"]) / 2, 1), 
        "Width_ft": data["width"],
        "Length_ft": data["length"],
        "Latitude": round(new_lat, 7),
        "Longitude": round(new_lon, 7),
        "Address": "252 E Utica St"
    })
    
    print(f"{sample_id:<10} | {data['width']}x{data['length']} ft | Lat: {new_lat:.6f}, Lon: {new_lon:.6f}")

# ==========================================
# 4. EXPORT TO CSV
# ==========================================
df_results = pd.DataFrame(results)
df_results.to_csv("Utica_Grid_Coordinates.csv", index=False)
print("\n✅ Successfully saved to Utica_Grid_Coordinates.csv!")