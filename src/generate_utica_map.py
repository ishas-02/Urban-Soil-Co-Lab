# # # import math
# # # import folium

# # # # --- 1. NYSH COLOR MAPPING ---
# # # def get_nysh_category(ppm):
# # #     if ppm < 63: return 'Safe (< 63 ppm)', '#2ecc71'
# # #     elif ppm < 100: return 'Elevated (63-99 ppm)', '#f1c40f'
# # #     elif ppm < 200: return 'Contaminated (100-199 ppm)', '#e67e22'
# # #     elif ppm < 400: return 'High (200-399 ppm)', '#e74c3c'
# # #     else: return 'Hazard (400+ ppm)', '#8e44ad'

# # # # --- 2. GPS OFFSET CALCULATOR ---
# # # def calculate_coordinate(start_lat, start_lon, offset_north_ft, offset_east_ft):
# # #     """Calculates a GPS coordinate based on an offset in feet from the anchor."""
# # #     R_EARTH_FT = 20925721.78 
# # #     delta_lat = (offset_north_ft / R_EARTH_FT) * (180 / math.pi)
# # #     lat_radians = start_lat * (math.pi / 180)
# # #     delta_lon = (offset_east_ft / (R_EARTH_FT * math.cos(lat_radians))) * (180 / math.pi)
# # #     return start_lat + delta_lat, start_lon + delta_lon

# # # # --- 3. SITE SETUP ---
# # # # Corner of Porch at 252 E Utica St
# # # ANCHOR_LAT = 42.9115083
# # # ANCHOR_LON = -78.8563833

# # # # We define the exact SW (Southwest) and NE (Northeast) corners of each block in feet
# # # # assuming the porch is (0,0) and the grid extends North and East.
# # # grid_layout = {
# # #     # ROW A (0 to 10 ft North)
# # #     "1A_Utica": {"sw_x": 0,  "sw_y": 0,  "ne_x": 7,  "ne_y": 10, "mock_ppm": 45},   # 7x10
# # #     "2A_Utica": {"sw_x": 7,  "sw_y": 0,  "ne_x": 17, "ne_y": 10, "mock_ppm": 85},   # 10x10
# # #     "3A_Utica": {"sw_x": 17, "sw_y": 0,  "ne_x": 27, "ne_y": 10, "mock_ppm": 120},  # 10x10

# # #     # ROW B (10 to 20 ft North)
# # #     "1B_Utica": {"sw_x": 0,  "sw_y": 10, "ne_x": 7,  "ne_y": 20, "mock_ppm": 60},   # 7x10
# # #     "2B_Utica": {"sw_x": 7,  "sw_y": 10, "ne_x": 17, "ne_y": 20, "mock_ppm": 180},  # 10x10
# # #     "3B_Utica": {"sw_x": 17, "sw_y": 10, "ne_x": 27, "ne_y": 20, "mock_ppm": 250},  # 10x10

# # #     # ROW C (20 to 30 ft North)
# # #     "1C_Utica": {"sw_x": 0,  "sw_y": 20, "ne_x": 7,  "ne_y": 30, "mock_ppm": 150},  # 7x10
# # #     "2C_Utica": {"sw_x": 7,  "sw_y": 20, "ne_x": 17, "ne_y": 30, "mock_ppm": 310},  # 10x10
# # #     "3C_Utica": {"sw_x": 17, "sw_y": 20, "ne_x": 27, "ne_y": 30, "mock_ppm": 450},  # 10x10

# # #     # ROW D (30 to 36 ft North)
# # #     "3D_Utica": {"sw_x": 17, "sw_y": 30, "ne_x": 27, "ne_y": 36, "mock_ppm": 520},  # 10x6
# # # }

# # # # --- 4. MAP GENERATION ---
# # # print("Generating exact rectangular heatmap for 252 E Utica St...")

# # # # Initialize map on the porch
# # # m = folium.Map(location=[ANCHOR_LAT, ANCHOR_LON], zoom_start=21, max_zoom=23)

# # # # Add Google Satellite View
# # # folium.TileLayer(
# # #     tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
# # #     attr='Google',
# # #     name='Google Satellite'
# # # ).add_to(m)

# # # # Draw the Anchor Point (Porch Corner)
# # # folium.Marker(
# # #     location=[ANCHOR_LAT, ANCHOR_LON],
# # #     tooltip="<b>Porch Corner (Anchor Point)</b>",
# # #     icon=folium.Icon(color='red', icon='home')
# # # ).add_to(m)

# # # # Draw all Rectangles
# # # for sample_id, dims in grid_layout.items():
# # #     # Calculate Southwest Corner (Bottom-Left)
# # #     sw_lat, sw_lon = calculate_coordinate(ANCHOR_LAT, ANCHOR_LON, dims["sw_y"], dims["sw_x"])
    
# # #     # Calculate Northeast Corner (Top-Right)
# # #     ne_lat, ne_lon = calculate_coordinate(ANCHOR_LAT, ANCHOR_LON, dims["ne_y"], dims["ne_x"])
    
# # #     # Get Color
# # #     ppm = dims["mock_ppm"]
# # #     label, color_hex = get_nysh_category(ppm)
    
# # #     # Calculate dimensions for the tooltip
# # #     width = dims["ne_x"] - dims["sw_x"]
# # #     length = dims["ne_y"] - dims["sw_y"]
    
# # #     tooltip_html = f"""
# # #     <div style='font-family: Arial; font-size: 14px;'>
# # #         <b>Sample:</b> {sample_id}<br>
# # #         <b>Size:</b> {width}x{length} ft<br>
# # #         <b>Mock Lead Level:</b> {ppm} ppm<br>
# # #         <b>NYSH Status:</b> {label}
# # #     </div>
# # #     """
    
# # #     # Draw the specific bounding box
# # #     folium.Rectangle(
# # #         bounds=[[sw_lat, sw_lon], [ne_lat, ne_lon]],
# # #         color='white',
# # #         weight=2,
# # #         fill=True,
# # #         fill_color=color_hex,
# # #         fill_opacity=0.75,
# # #         tooltip=tooltip_html
# # #     ).add_to(m)

# # # # --- 5. SAVE AND EXPORT ---
# # # output_file = "utica_heatmap.html"
# # # m.save(output_file)
# # # print(f"✅ Map successfully generated! Open '{output_file}' in your web browser to view it.")

# # import math
# # import folium

# # # --- 1. NYSH COLOR MAPPING ---
# # def get_nysh_category(ppm):
# #     if ppm < 63: return 'Safe (< 63 ppm)', '#2ecc71'
# #     elif ppm < 100: return 'Elevated (63-99 ppm)', '#f1c40f'
# #     elif ppm < 200: return 'Contaminated (100-199 ppm)', '#e67e22'
# #     elif ppm < 400: return 'High (200-399 ppm)', '#e74c3c'
# #     else: return 'Hazard (400+ ppm)', '#8e44ad'

# # # --- 2. GPS OFFSET CALCULATOR ---
# # def calculate_coordinate(start_lat, start_lon, offset_north_ft, offset_east_ft):
# #     """Calculates a GPS coordinate based on an offset in feet from the anchor."""
# #     R_EARTH_FT = 20925721.78 
# #     delta_lat = (offset_north_ft / R_EARTH_FT) * (180 / math.pi)
# #     lat_radians = start_lat * (math.pi / 180)
# #     delta_lon = (offset_east_ft / (R_EARTH_FT * math.cos(lat_radians))) * (180 / math.pi)
# #     return start_lat + delta_lat, start_lon + delta_lon

# # # --- 3. SITE SETUP ---
# # # Corner of Porch at 252 E Utica St (Your Anchor Point)
# # ANCHOR_LAT = 42.9115083
# # ANCHOR_LON = -78.8563833

# # # Defining the exact Southwest (sw) and Northeast (ne) corners of each block in feet.
# # # This aligns perfectly with your mockup where the anchor is at the bottom-left.
# # grid_layout = {
# #     # COLUMN 1 (Left, 7ft wide)
# #     "1A_Utica": {"sw_x": 0, "sw_y": 0,  "ne_x": 7, "ne_y": 10, "mock_ppm": 45},  # Green
# #     "1B_Utica": {"sw_x": 0, "sw_y": 10, "ne_x": 7, "ne_y": 20, "mock_ppm": 45},  # Green
# #     "1C_Utica": {"sw_x": 0, "sw_y": 20, "ne_x": 7, "ne_y": 30, "mock_ppm": 150}, # Orange

# #     # COLUMN 2 (Middle, 10ft wide)
# #     "2A_Utica": {"sw_x": 7, "sw_y": 0,  "ne_x": 17, "ne_y": 10, "mock_ppm": 85},  # Yellow
# #     "2B_Utica": {"sw_x": 7, "sw_y": 10, "ne_x": 17, "ne_y": 20, "mock_ppm": 150}, # Orange
# #     "2C_Utica": {"sw_x": 7, "sw_y": 20, "ne_x": 17, "ne_y": 30, "mock_ppm": 250}, # Red

# #     # COLUMN 3 (Right, 10ft wide)
# #     "3A_Utica": {"sw_x": 17, "sw_y": 0,  "ne_x": 27, "ne_y": 10, "mock_ppm": 150}, # Orange
# #     "3B_Utica": {"sw_x": 17, "sw_y": 10, "ne_x": 27, "ne_y": 20, "mock_ppm": 250}, # Red
# #     "3C_Utica": {"sw_x": 17, "sw_y": 20, "ne_x": 27, "ne_y": 30, "mock_ppm": 450}, # Purple

# #     # EXTENSION 3D (Above Column 3, 10x6 ft)
# #     "3D_Utica": {"sw_x": 17, "sw_y": 30, "ne_x": 27, "ne_y": 36, "mock_ppm": 450}, # Purple
# # }

# # # --- 4. MAP GENERATION ---
# # print("Generating real-world satellite heatmap for 252 E Utica St...")

# # # Initialize map focused on the porch
# # m = folium.Map(location=[ANCHOR_LAT, ANCHOR_LON], zoom_start=21, max_zoom=23)

# # # Add Google Satellite View
# # folium.TileLayer(
# #     tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
# #     attr='Google',
# #     name='Google Satellite'
# # ).add_to(m)

# # # Draw the Anchor Point (Porch Corner) to match the red home icon in your mockup
# # folium.Marker(
# #     location=[ANCHOR_LAT, ANCHOR_LON],
# #     tooltip="<b>Porch Corner (Anchor Point)</b>",
# #     icon=folium.Icon(color='red', icon='home')
# # ).add_to(m)

# # # Draw all Rectangles
# # for sample_id, dims in grid_layout.items():
# #     # Calculate Southwest Corner (Bottom-Left)
# #     sw_lat, sw_lon = calculate_coordinate(ANCHOR_LAT, ANCHOR_LON, dims["sw_y"], dims["sw_x"])
    
# #     # Calculate Northeast Corner (Top-Right)
# #     ne_lat, ne_lon = calculate_coordinate(ANCHOR_LAT, ANCHOR_LON, dims["ne_y"], dims["ne_x"])
    
# #     # Get Color
# #     ppm = dims["mock_ppm"]
# #     label, color_hex = get_nysh_category(ppm)
    
# #     # Calculate dimensions for the tooltip
# #     width = dims["ne_x"] - dims["sw_x"]
# #     length = dims["ne_y"] - dims["sw_y"]
    
# #     tooltip_html = f"""
# #     <div style='font-family: Arial; font-size: 14px;'>
# #         <b>Sample:</b> {sample_id}<br>
# #         <b>Size:</b> {width}x{length} ft<br>
# #         <b>Mock Lead Level:</b> {ppm} ppm<br>
# #         <b>NYSH Status:</b> {label}
# #     </div>
# #     """
    
# #     # Draw the specific bounding box
# #     folium.Rectangle(
# #         bounds=[[sw_lat, sw_lon], [ne_lat, ne_lon]],
# #         color='white',
# #         weight=2,
# #         fill=True,
# #         fill_color=color_hex,
# #         fill_opacity=0.8,
# #         tooltip=tooltip_html
# #     ).add_to(m)

# # # --- 5. SAVE AND EXPORT ---
# # output_file = "utica_satellite_heatmap.html"
# # m.save(output_file)
# # print(f"✅ Map successfully generated! Open '{output_file}' in your web browser to view it.")

# import math
# import folium

# # --- 1. NYSH COLOR MAPPING ---
# def get_nysh_category(ppm):
#     # Action levels based on NYSH guidance
#     if ppm < 63: return 'Safe (< 63 ppm)', '#2ecc71'
#     elif ppm < 100: return 'Elevated (63-99 ppm)', '#f1c40f'
#     elif ppm < 200: return 'Contaminated (100-199 ppm)', '#e67e22'
#     elif ppm < 400: return 'High (200-399 ppm)', '#e74c3c'
#     else: return 'Hazard (400+ ppm)', '#8e44ad'

# # --- 2. GPS OFFSET CALCULATOR ---
# def calculate_coordinate(start_lat, start_lon, offset_north_ft, offset_east_ft):
#     R_EARTH_FT = 20925721.78 
#     delta_lat = (offset_north_ft / R_EARTH_FT) * (180 / math.pi)
#     lat_radians = start_lat * (math.pi / 180)
#     delta_lon = (offset_east_ft / (R_EARTH_FT * math.cos(lat_radians))) * (180 / math.pi)
#     return start_lat + delta_lat, start_lon + delta_lon

# # --- 3. SITE SETUP ---
# # Porch Corner at 252 E Utica St
# ANCHOR_LAT = 42.9115083
# ANCHOR_LON = -78.8563833

# # Exact grid layouts using your dimensions (7x10, 10x10, 10x6)
# grid_layout = {
#     # COLUMN 1 (Left, 7ft wide)
#     "1A_Utica": {"sw_x": 0, "sw_y": 0,  "ne_x": 7, "ne_y": 10, "mock_ppm": 45},  
#     "1B_Utica": {"sw_x": 0, "sw_y": 10, "ne_x": 7, "ne_y": 20, "mock_ppm": 45},  
#     "1C_Utica": {"sw_x": 0, "sw_y": 20, "ne_x": 7, "ne_y": 30, "mock_ppm": 150}, 

#     # COLUMN 2 (Middle, 10ft wide)
#     "2A_Utica": {"sw_x": 7, "sw_y": 0,  "ne_x": 17, "ne_y": 10, "mock_ppm": 85},  
#     "2B_Utica": {"sw_x": 7, "sw_y": 10, "ne_x": 17, "ne_y": 20, "mock_ppm": 150}, 
#     "2C_Utica": {"sw_x": 7, "sw_y": 20, "ne_x": 17, "ne_y": 30, "mock_ppm": 250}, 

#     # COLUMN 3 (Right, 10ft wide)
#     "3A_Utica": {"sw_x": 17, "sw_y": 0,  "ne_x": 27, "ne_y": 10, "mock_ppm": 150}, 
#     "3B_Utica": {"sw_x": 17, "sw_y": 10, "ne_x": 27, "ne_y": 20, "mock_ppm": 250}, 
#     "3C_Utica": {"sw_x": 17, "sw_y": 20, "ne_x": 27, "ne_y": 30, "mock_ppm": 450}, 

#     # EXTENSION 3D (Above Column 3, 10x6 ft)
#     "3D_Utica": {"sw_x": 17, "sw_y": 30, "ne_x": 27, "ne_y": 36, "mock_ppm": 450}, 
# }

# # --- 4. MAP GENERATION ---
# print("Generating high-resolution satellite grid for 252 E Utica St...")

# # Initialize map using Esri World Imagery (Extremely reliable satellite view)
# m = folium.Map(location=[ANCHOR_LAT + 0.00005, ANCHOR_LON + 0.00003], zoom_start=21, max_zoom=23, tiles=None)

# # Add the Satellite Layer
# folium.TileLayer(
#     tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
#     attr='Esri',
#     name='Esri Satellite',
#     overlay=False,
#     control=True
# ).add_to(m)

# # Draw the Anchor Point (Porch Corner)
# folium.Marker(
#     location=[ANCHOR_LAT, ANCHOR_LON],
#     tooltip="<b>Porch Corner (Anchor Point)</b>",
#     icon=folium.Icon(color='red', icon='home')
# ).add_to(m)

# # Draw all colored Rectangles
# for sample_id, dims in grid_layout.items():
#     sw_lat, sw_lon = calculate_coordinate(ANCHOR_LAT, ANCHOR_LON, dims["sw_y"], dims["sw_x"])
#     ne_lat, ne_lon = calculate_coordinate(ANCHOR_LAT, ANCHOR_LON, dims["ne_y"], dims["ne_x"])
    
#     ppm = dims["mock_ppm"]
#     label, color_hex = get_nysh_category(ppm)
    
#     width = dims["ne_x"] - dims["sw_x"]
#     length = dims["ne_y"] - dims["sw_y"]
    
#     tooltip_html = f"""
#     <div style='font-family: Arial; font-size: 14px;'>
#         <b>Sample:</b> {sample_id}<br>
#         <b>Size:</b> {width}x{length} ft<br>
#         <b>Mock Lead Level:</b> {ppm} ppm<br>
#         <b>NYSH Status:</b> {label}
#     </div>
#     """
    
#     folium.Rectangle(
#         bounds=[[sw_lat, sw_lon], [ne_lat, ne_lon]],
#         color='white',
#         weight=2,
#         fill=True,
#         fill_color=color_hex,
#         fill_opacity=0.75, # Semi-transparent to see the yard underneath
#         tooltip=tooltip_html
#     ).add_to(m)

# # --- 5. SAVE AND EXPORT ---
# output_file = "utica_satellite_grid.html"
# m.save(output_file)
# print(f"✅ Map successfully generated! Open '{output_file}' in your web browser.")

import math
import folium

# --- 1. NYSH COLOR MAPPING ---
def get_nysh_category(ppm):
    # Action levels based on NYSH guidance 
    if ppm < 63: return 'Safe (< 63 ppm)', '#2ecc71' # Within typical background levels 
    elif ppm < 100: return 'Elevated (63-99 ppm)', '#f1c40f' # Levels are above background levels 
    elif ppm < 200: return 'Contaminated (100-199 ppm)', '#e67e22' # Levels suggest lead contamination 
    elif ppm < 400: return 'High (200-399 ppm)', '#e74c3c' # Levels are above the US EPA Jan 2024 regional screening level guidance 
    else: return 'Hazard (400+ ppm)', '#8e44ad' # Suggests significant contamination 

# --- 2. GPS OFFSET CALCULATOR ---
def calculate_coordinate(start_lat, start_lon, offset_north_ft, offset_east_ft):
    """Calculates a GPS coordinate based on an offset in feet. Handles negatives (South/West) automatically."""
    R_EARTH_FT = 20925721.78 
    delta_lat = (offset_north_ft / R_EARTH_FT) * (180 / math.pi)
    lat_radians = start_lat * (math.pi / 180)
    delta_lon = (offset_east_ft / (R_EARTH_FT * math.cos(lat_radians))) * (180 / math.pi)
    return start_lat + delta_lat, start_lon + delta_lon

# --- 3. SITE SETUP ---
# Corner of Porch at 252 E Utica St (The intersection of 3D, 3C, and 2C)
ANCHOR_LAT = 42.9115083
ANCHOR_LON = -78.8563833

# The grid is now plotted relative to the inner intersection.
# Positive Y is North. Negative Y is South.
# Positive X is East. Negative X is West.
grid_layout = {
    # COLUMN 1 (Far Left/West, 7ft wide)
    "1A_Utica": {"sw_x": -17, "sw_y": 20, "ne_x": -10, "ne_y": 30, "mock_ppm": 45},  
    "1B_Utica": {"sw_x": -17, "sw_y": 10, "ne_x": -10, "ne_y": 20, "mock_ppm": 45},  
    "1C_Utica": {"sw_x": -17, "sw_y": 0,  "ne_x": -10, "ne_y": 10, "mock_ppm": 150}, 

    # COLUMN 2 (Middle Left/West, 10ft wide)
    "2A_Utica": {"sw_x": -10, "sw_y": 20, "ne_x": 0,   "ne_y": 30, "mock_ppm": 85},  
    "2B_Utica": {"sw_x": -10, "sw_y": 10, "ne_x": 0,   "ne_y": 20, "mock_ppm": 150}, 
    "2C_Utica": {"sw_x": -10, "sw_y": 0,  "ne_x": 0,   "ne_y": 10, "mock_ppm": 250}, 

    # COLUMN 3 (Right/East side, starting at Anchor X=0, 10ft wide)
    "3A_Utica": {"sw_x": 0,   "sw_y": 20, "ne_x": 10,  "ne_y": 30, "mock_ppm": 150}, 
    "3B_Utica": {"sw_x": 0,   "sw_y": 10, "ne_x": 10,  "ne_y": 20, "mock_ppm": 250}, 
    "3C_Utica": {"sw_x": 0,   "sw_y": 0,  "ne_x": 10,  "ne_y": 10, "mock_ppm": 450}, 

    # EXTENSION 3D (Below 3C, 10x6 ft)
    # This block drops South (Negative Y) of the anchor!
    "3D_Utica": {"sw_x": 0,   "sw_y": -6, "ne_x": 10,  "ne_y": 0,  "mock_ppm": 450}, 
}

# --- 4. MAP GENERATION ---
print("Generating fixed-anchor high-resolution satellite grid...")

# Initialize map (centered slightly North and West of the porch to show the whole backyard grid)
m = folium.Map(location=[ANCHOR_LAT + 0.00004, ANCHOR_LON - 0.00002], zoom_start=21, max_zoom=25, tiles=None)

# High-Res Esri Satellite Layer (with zoom unlock)
folium.TileLayer(
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attr='Esri',
    name='Esri Satellite',
    max_zoom=25,
    max_native_zoom=19,
    overlay=False,
    control=True
).add_to(m)

# Draw the Anchor Point (Porch Corner)
folium.Marker(
    location=[ANCHOR_LAT, ANCHOR_LON],
    tooltip="<b>Porch Corner (Anchor Point at 3D/3C/2C)</b>",
    icon=folium.Icon(color='red', icon='home')
).add_to(m)

# Draw all colored Rectangles
for sample_id, dims in grid_layout.items():
    sw_lat, sw_lon = calculate_coordinate(ANCHOR_LAT, ANCHOR_LON, dims["sw_y"], dims["sw_x"])
    ne_lat, ne_lon = calculate_coordinate(ANCHOR_LAT, ANCHOR_LON, dims["ne_y"], dims["ne_x"])
    
    ppm = dims["mock_ppm"]
    label, color_hex = get_nysh_category(ppm)
    
    width = dims["ne_x"] - dims["sw_x"]
    length = dims["ne_y"] - dims["sw_y"]
    
    tooltip_html = f"""
    <div style='font-family: Arial; font-size: 14px;'>
        <b>Sample:</b> {sample_id}<br>
        <b>Size:</b> {width}x{length} ft<br>
        <b>Mock Lead Level:</b> {ppm} ppm<br>
        <b>NYSH Status:</b> {label}
    </div>
    """
    
    folium.Rectangle(
        bounds=[[sw_lat, sw_lon], [ne_lat, ne_lon]],
        color='white',
        weight=2,
        fill=True,
        fill_color=color_hex,
        fill_opacity=0.75, 
        tooltip=tooltip_html
    ).add_to(m)

# --- 5. SAVE AND EXPORT ---
output_file = "utica_satellite_grid_corrected.html"
m.save(output_file)
print(f"✅ Map successfully generated! Open '{output_file}' in your web browser.")