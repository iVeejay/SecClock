import io, requests, threading, json, os, sys
from datetime import datetime
from PIL import Image, ImageTk, ImageDraw, ImageFont
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pystray
from pystray import MenuItem as item
import win32api, win32con, win32gui
import webbrowser

# Paths
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(BASE_DIR, "assets", "SecClock.ico")
FONT_PATH = os.path.join(BASE_DIR, "fonts", "Blooming.otf")

# Separate mask paths for each size
MASK_PATHS = {
    "small": os.path.join(BASE_DIR, "assets", "mask_small.png"),
    "medium": os.path.join(BASE_DIR, "assets", "mask_medium.png"),
    "large": os.path.join(BASE_DIR, "assets", "mask_large.png")
}

# Social Media Icons
SOCIAL_ICONS = {
    "discord": os.path.join(BASE_DIR, "assets", "discord.png"),
    "github": os.path.join(BASE_DIR, "assets", "github.png"),
    "instagram": os.path.join(BASE_DIR, "assets", "insta.png"),
    "youtube": os.path.join(BASE_DIR, "assets", "yt.png")
}

# Window Size Presets (maintaining 480x270 ratio)
SIZE_PRESETS = {
    "small": (360, 203),    # 75% of medium
    "medium": (480, 270),   # original size
    "large": (600, 338)     # 125% of medium
}

# Default settings
DEFAULT_SETTINGS = {
    "font_size": 46,
    "font_color": "#FFFFFF",
    "custom_bg_image": "",
    "remember_position": True,
    "lock_dragging": False,
    "run_on_startup": False,
    "window_x": 50,
    "window_y": 50,
    "window_size": "medium",  # small, medium, large
    "current_bg_url": ""      # Store current background to prevent reloading
}

# Social Media Links (Replace with your actual links)
SOCIAL_LINKS = {
    "discord": "https://discord.com/invite/5GwKeR9eve",
    "instagram": "https://www.instagram.com/iveejays", 
    "youtube": "https://www.youtube.com/@iVeejay",
    "github": "https://github.com/iVeejay"
}

# Settings window colors - ONLY these two colors are used
SETTINGS_BG = "#2d2d2d"
SETTINGS_FG = "#ffffff"

class SettingsManager:
    def __init__(self):
        self.settings_file = os.path.join(BASE_DIR, "settings.json")
        self.settings = self.load_settings()
    
    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    # Merge with defaults, preserving current_bg_url if it exists
                    result = {**DEFAULT_SETTINGS, **loaded_settings}
                    # Ensure window_size is valid
                    if result["window_size"] not in SIZE_PRESETS:
                        result["window_size"] = "medium"
                    return result
        except:
            pass
        return DEFAULT_SETTINGS.copy()
    
    def save_settings(self):
        try:
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
            return True
        except:
            return False
    
    def get(self, key):
        return self.settings.get(key, DEFAULT_SETTINGS.get(key))
    
    def set(self, key, value):
        self.settings[key] = value
        self.save_settings()

class SecClock:
    def __init__(self):
        self.settings = SettingsManager()
        
        # Create main window FIRST and make it visible
        self.root = tk.Tk()
        self.root.title("SecClock")
        
        # Set app icon
        try:
            if os.path.exists(ICON_PATH):
                self.root.iconbitmap(ICON_PATH)
        except:
            pass
        
        self.root.overrideredirect(True)
        
        # Set window position and size from settings
        x = self.settings.get("window_x")
        y = self.settings.get("window_y")
        size_preset = self.settings.get("window_size")
        self.SIZE = SIZE_PRESETS[size_preset]
        self.current_size_preset = size_preset
        
        self.root.geometry(f"{self.SIZE[0]}x{self.SIZE[1]}+{x}+{y}")
        
        self.root.attributes("-topmost", True)
        self.root.wm_attributes("-transparentcolor", "magenta")
        
        self.url_index = 0
        self.custom_font = None
        self.custom_bg_images = []
        self.current_bg_url = self.settings.get("current_bg_url")
        
        # Initialize
        self.load_custom_font()
        self.load_custom_background()
        
        # Store current time parts
        self.current_hours = ""
        self.current_minutes = "" 
        self.current_seconds = ""
        
        # Canvas items
        self.hours_item = None
        self.minutes_item = None
        self.seconds_item = None
        self.colon1_item = None
        self.colon2_item = None
        
        self.hours_image = None
        self.minutes_image = None
        self.seconds_image = None
        self.colon1_image = None
        self.colon2_image = None
        
        # Create UI
        self.create_ui()
        
        # Bind window close event
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        
        # Setup tray icon AFTER UI is created
        self.setup_tray_icon()
        
        # Start clock
        self._tick()
        
    def load_custom_font(self):
        try:
            font_size = self.settings.get("font_size")
            self.custom_font = ImageFont.truetype(FONT_PATH, font_size)
            print(f"Font loaded: {FONT_PATH}, Size: {font_size}")
        except Exception as e:
            print(f"Error loading custom font: {e}")
            self.custom_font = None
    
    def load_custom_background(self):
        custom_bg = self.settings.get("custom_bg_image")
        if custom_bg and os.path.exists(custom_bg):
            self.custom_bg_images = [custom_bg]
            print(f"Custom background loaded: {custom_bg}")
        else:
            self.custom_bg_images = []
            print("Using default online backgrounds")
    
    def load_mask_for_size(self, size_preset):
        """Load the appropriate mask for the given size preset"""
        try:
            mask_path = MASK_PATHS.get(size_preset)
            if mask_path and os.path.exists(mask_path):
                mask = Image.open(mask_path).convert("L")
                # Verify mask size matches expected size
                expected_size = SIZE_PRESETS[size_preset]
                if mask.size != expected_size:
                    print(f"Warning: Mask size {mask.size} doesn't match expected size {expected_size} for {size_preset}")
                    # Resize mask to correct size
                    mask = mask.resize(expected_size, Image.LANCZOS)
                print(f"Mask loaded successfully for {size_preset}: {mask_path}")
                return mask
            else:
                print(f"Mask file not found for {size_preset}: {mask_path}")
                # Fallback: create dynamic mask
                return self.create_dynamic_mask(SIZE_PRESETS[size_preset])
        except Exception as e:
            print(f"Error loading mask for {size_preset}: {e}")
            # Fallback: create dynamic mask
            return self.create_dynamic_mask(SIZE_PRESETS[size_preset])
    
    def create_dynamic_mask(self, size):
        """Fallback: create a dynamic mask if separate mask files are missing"""
        width, height = size
        radius = min(60, height // 4)  # Smaller radius for smaller windows
        
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        
        # Draw main rectangle (top part - straight edges)
        draw.rectangle([0, 0, width, height - radius], fill=255)
        
        # Draw bottom part with rounded corners
        draw.pieslice([0, height - 2*radius, 2*radius, height], 90, 180, fill=255)
        draw.pieslice([width - 2*radius, height - 2*radius, width, height], 0, 90, fill=255)
        draw.rectangle([radius, height - radius, width - radius, height], fill=255)
        draw.polygon([(0, height - radius), (radius, height - radius), (0, height)], fill=255)
        draw.polygon([(width, height - radius), (width - radius, height - radius), (width, height)], fill=255)
        
        print(f"Created dynamic fallback mask for size {size}")
        return mask
    
    def create_text_image(self, text, font, color=None, fixed_width=None):
        if color is None:
            color = self.settings.get("font_color")
            
        # Create a temporary image to measure text size
        temp_img = Image.new("RGB", (1, 1))
        temp_draw = ImageDraw.Draw(temp_img)
        
        if font:
            bbox = temp_draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0] + 20  # More padding
            text_height = bbox[3] - bbox[1] + 20
        else:
            # Fallback if font is None
            text_width = 60
            text_height = 60
        
        if fixed_width:
            text_width = fixed_width
        
        # Create transparent image for text
        text_img = Image.new("RGBA", (text_width, text_height), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_img)
        
        # Draw text centered
        if font:
            text_draw.text((text_width // 2, text_height // 2), text, fill=color, font=font, anchor="mm")
        else:
            # Fallback: use default font
            fallback_font = ImageFont.load_default()
            text_draw.text((text_width // 2, text_height // 2), text, fill=color, font=fallback_font, anchor="mm")
        
        return ImageTk.PhotoImage(text_img), text_width
    
    def download_image(self, url):
        try:
            print(f"Downloading background: {url}")
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            im = Image.open(io.BytesIO(r.content)).convert("RGB")
            im = im.resize(self.SIZE, Image.LANCZOS)  # This uses current self.SIZE
            
            # Load the appropriate mask for current size
            mask = self.load_mask_for_size(self.current_size_preset)
            im_rgba = im.convert("RGBA")
            
            # Apply mask
            im_rgba.putalpha(mask)
            
            print("Background downloaded successfully")
            return ImageTk.PhotoImage(im_rgba)
        except Exception as e:
            print(f"Error downloading background: {e}")
            return None

    def load_local_image(self, path):
        try:
            print(f"Loading local image: {path}")
            im = Image.open(path).convert("RGB")
            im = im.resize(self.SIZE, Image.LANCZOS)  # This uses current self.SIZE
            
            # Load the appropriate mask for current size
            mask = self.load_mask_for_size(self.current_size_preset)
            im_rgba = im.convert("RGBA")
            
            # Apply mask
            im_rgba.putalpha(mask)
            
            print("Local image loaded successfully")
            return ImageTk.PhotoImage(im_rgba)
        except Exception as e:
            print(f"Error loading local image: {e}")
            return None
        
    def create_ui(self):
        print("Creating UI...")
        
        self.canvas = tk.Canvas(
            self.root,
            width=self.SIZE[0],
            height=self.SIZE[1],
            highlightthickness=0,
            bg="magenta"
        )
        self.canvas.pack(fill="both", expand=True)

        # Load background (don't reload if we already have one)
        if not hasattr(self, 'bg') or self.bg is None:
            self.load_current_background()
        
        # Create clock
        self._create_separated_clock()

        # Settings button (gear icon)
        self.settings_btn = tk.Button(
            self.root,
            text="⚙",
            command=self.show_settings,
            relief="flat",
            bg="#333333",
            activebackground="#555555",
            fg="white",
            borderwidth=0,
            cursor="hand2",
            font=("Arial", 10, "bold")
        )
        self.settings_btn.place(x=10, y=10, width=25, height=25)

        # Close button
        self.close_btn = tk.Button(
            self.root,
            text="✕",
            command=self.hide_to_tray,
            relief="flat",
            bg="#FF4444", 
            activebackground="#FF6666",
            fg="white",
            borderwidth=0,
            cursor="hand2",
            font=("Arial", 12, "bold")
        )
        self.close_btn.place(x=self.SIZE[0]-35, y=10, width=25, height=25)

        # Background change button
        self.bg_btn = tk.Button(
            self.root,
            text="↻", 
            command=self.change_background_threaded,
            relief="flat",
            bg="#333333",
            activebackground="#555555",
            fg="white",
            borderwidth=0,
            cursor="hand2", 
            font=("Arial", 12, "bold")
        )
        self.bg_btn.place(x=self.SIZE[0]-70, y=10, width=25, height=25)

        # Dragging (if not locked)
        if not self.settings.get("lock_dragging"):
            self._drag_dx = 0
            self._drag_dy = 0
            self.canvas.bind("<Button-1>", self._start_drag)
            self.canvas.bind("<B1-Motion>", self._on_drag)
            
        print("UI created successfully")
    
    def load_current_background(self):
        print("Loading current background...")
        
        # Clear existing background to force reload
        self.bg = None
        
        if self.custom_bg_images:
            # Use custom background
            self.bg = self.load_local_image(self.custom_bg_images[0])
            print(f"Loaded custom background: {self.custom_bg_images[0]}")
        else:
            # Use online backgrounds
            IMG_URLS = [
                "https://picsum.photos/800/600",
                "https://loremflickr.com/800/600/nature", 
                "https://picsum.photos/seed/pic1/800/600",
            ]
            
            # Use current URL if available, otherwise get new one
            if self.current_bg_url and self.current_bg_url in IMG_URLS:
                url_index = IMG_URLS.index(self.current_bg_url)
                self.bg = self.download_image(self.current_bg_url)
                self.url_index = url_index
                print(f"Reloaded existing online background: {self.current_bg_url}")
            else:
                self.bg = self.download_image(IMG_URLS[self.url_index])
                self.current_bg_url = IMG_URLS[self.url_index]
                self.settings.set("current_bg_url", self.current_bg_url)
                print(f"Loaded new online background: {self.current_bg_url}")
        
        if self.bg:
            # Remove old background item if it exists
            if hasattr(self, 'bg_item'):
                self.canvas.delete(self.bg_item)
            self.bg_item = self.canvas.create_image(0, 0, anchor="nw", image=self.bg)
            # Make sure background is behind everything
            self.canvas.lower(self.bg_item)
            print("Background set successfully")
        else:
            print("Failed to load background - using fallback")
            # Create a fallback background with proper masking
            fallback_bg = Image.new("RGB", self.SIZE, "#333333")
            mask = self.load_mask_for_size(self.current_size_preset)
            fallback_bg_rgba = fallback_bg.convert("RGBA")
            fallback_bg_rgba.putalpha(mask)
            self.bg = ImageTk.PhotoImage(fallback_bg_rgba)
            # Remove old background item if it exists
            if hasattr(self, 'bg_item'):
                self.canvas.delete(self.bg_item)
            self.bg_item = self.canvas.create_image(0, 0, anchor="nw", image=self.bg)
            # Make sure background is behind everything
            self.canvas.lower(self.bg_item)
    
    def _create_separated_clock(self):
        print("Creating separated clock...")
        
        current_time = datetime.now()
        hours = current_time.strftime("%H")
        minutes = current_time.strftime("%M") 
        seconds = current_time.strftime("%S")
        
        self.current_hours = hours
        self.current_minutes = minutes
        self.current_seconds = seconds
        
        center_x = self.SIZE[0] // 2
        center_y = self.SIZE[1] // 2
        
        if self.custom_font:
            print("Using custom font for clock")
            hours_img, hours_width = self.create_text_image(hours, self.custom_font)
            minutes_img, minutes_width = self.create_text_image(minutes, self.custom_font)
            seconds_img, seconds_width = self.create_text_image(seconds, self.custom_font)
            colon_img, colon_width = self.create_text_image(":", self.custom_font, fixed_width=20)
            
            total_width = hours_width + colon_width + minutes_width + colon_width + seconds_width
            start_x = center_x - total_width // 2
            current_x = start_x
            
            # Hours
            self.hours_item = self.canvas.create_image(
                current_x + hours_width // 2, center_y, image=hours_img, anchor="center"
            )
            self.hours_image = hours_img
            current_x += hours_width
            
            # First colon
            self.colon1_item = self.canvas.create_image(
                current_x + colon_width // 2, center_y, image=colon_img, anchor="center"
            )
            self.colon1_image = colon_img
            current_x += colon_width
            
            # Minutes  
            self.minutes_item = self.canvas.create_image(
                current_x + minutes_width // 2, center_y, image=minutes_img, anchor="center"
            )
            self.minutes_image = minutes_img
            current_x += minutes_width
            
            # Second colon
            self.colon2_item = self.canvas.create_image(
                current_x + colon_width // 2, center_y, image=colon_img, anchor="center"
            )
            self.colon2_image = colon_img
            current_x += colon_width
            
            # Seconds
            self.seconds_item = self.canvas.create_image(
                current_x + seconds_width // 2, center_y, image=seconds_img, anchor="center"
            )
            self.seconds_image = seconds_img
            
        else:
            print("Using fallback font for clock")
            time_str = f"{hours}:{minutes}:{seconds}"
            self.hours_item = self.canvas.create_text(
                center_x, center_y, text=time_str,
                fill=self.settings.get("font_color"),
                font=("Arial", self.settings.get("font_size"), "bold"),
                anchor="center"
            )
        
        print("Clock created successfully")
    
    def _update_separated_clock(self):
        current_time = datetime.now()
        new_hours = current_time.strftime("%H")
        new_minutes = current_time.strftime("%M")
        new_seconds = current_time.strftime("%S")
        
        if self.custom_font:
            if new_hours != self.current_hours and self.hours_item:
                hours_img, _ = self.create_text_image(new_hours, self.custom_font)
                self.canvas.itemconfig(self.hours_item, image=hours_img)
                self.hours_image = hours_img
                self.current_hours = new_hours
            
            if new_minutes != self.current_minutes and self.minutes_item:
                minutes_img, _ = self.create_text_image(new_minutes, self.custom_font)
                self.canvas.itemconfig(self.minutes_item, image=minutes_img)
                self.minutes_image = minutes_img
                self.current_minutes = new_minutes
            
            if new_seconds != self.current_seconds and self.seconds_item:
                seconds_img, _ = self.create_text_image(new_seconds, self.custom_font)
                self.canvas.itemconfig(self.seconds_item, image=seconds_img)
                self.seconds_image = seconds_img
                self.current_seconds = new_seconds
                
        else:
            if new_seconds != self.current_seconds and self.hours_item:
                time_str = f"{new_hours}:{new_minutes}:{new_seconds}"
                self.canvas.itemconfig(self.hours_item, text=time_str)
                self.current_hours = new_hours
                self.current_minutes = new_minutes
                self.current_seconds = new_seconds
    
    def _start_drag(self, event):
        if any([
            (10 <= event.x <= 35 and 10 <= event.y <= 35),  # Settings button
            (self.SIZE[0]-70 <= event.x <= self.SIZE[0]-45 and 10 <= event.y <= 35),  # BG button
            (self.SIZE[0]-35 <= event.x <= self.SIZE[0]-10 and 10 <= event.y <= 35)   # Close button
        ]):
            return
        self._drag_dx = event.x
        self._drag_dy = event.y
    
    def _on_drag(self, event):
        if hasattr(self, '_drag_dx'):
            x = self.root.winfo_x() + event.x - self._drag_dx
            y = self.root.winfo_y() + event.y - self._drag_dy
            self.root.geometry(f"+{x}+{y}")
            
            # Save position if remember position is enabled
            if self.settings.get("remember_position"):
                self.settings.set("window_x", x)
                self.settings.set("window_y", y)
    
    def _tick(self):
        self._update_separated_clock()
        self.root.after(200, self._tick)
    
    def change_background_threaded(self):
        threading.Thread(target=self._change_background, daemon=True).start()
    
    def _change_background(self):
        try:
            IMG_URLS = [
                "https://picsum.photos/800/600",
                "https://loremflickr.com/800/600/nature", 
                "https://picsum.photos/seed/pic1/800/600",
            ]
            
            if self.custom_bg_images:
                # Cycle through custom backgrounds
                current_index = 0
                if hasattr(self, 'current_custom_bg_index'):
                    current_index = (self.current_custom_bg_index + 1) % len(self.custom_bg_images)
                else:
                    self.current_custom_bg_index = 0
                
                self.current_custom_bg_index = current_index
                new_bg = self.load_local_image(self.custom_bg_images[current_index])
            else:
                # Cycle through online backgrounds
                self.url_index = (self.url_index + 1) % len(IMG_URLS)
                new_bg = self.download_image(IMG_URLS[self.url_index])
                self.current_bg_url = IMG_URLS[self.url_index]
                self.settings.set("current_bg_url", self.current_bg_url)
            
            if new_bg:
                self.bg = new_bg
                self.root.after(0, lambda: self.canvas.itemconfig(self.bg_item, image=self.bg))
        except Exception as ex:
            print("Background load failed:", ex)
    
    def show_settings(self):
        try:
            SettingsWindow(self)
        except Exception as e:
            print(f"Error opening settings: {e}")
    
    def hide_to_tray(self):
        """Safely hide window to tray"""
        try:
            self.root.withdraw()
        except Exception as e:
            print(f"Error hiding to tray: {e}")
    
    def show_from_tray(self):
        """Safely show window from tray"""
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception as e:
            print(f"Error showing from tray: {e}")
    
    def quit_app(self):
        """Safely quit application"""
        try:
            if hasattr(self, 'tray_icon'):
                self.tray_icon.stop()
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            print(f"Error quitting app: {e}")
            os._exit(0)
    
    def setup_tray_icon(self):
        try:
            # Create a simple icon if the file doesn't exist
            if os.path.exists(ICON_PATH):
                image = Image.open(ICON_PATH)
            else:
                # Create a simple default icon
                image = Image.new('RGB', (64, 64), '#333333')
                draw = ImageDraw.Draw(image)
                draw.rectangle([16, 16, 48, 48], fill='#FFFFFF')
                print("Created fallback tray icon")
            
            menu = (
                item('Show SecClock', lambda: self.show_from_tray()),
                item('Settings', lambda: self.show_settings()),
                item('Exit', lambda: self.quit_app())
            )
            
            self.tray_icon = pystray.Icon("SecClock", image, "SecClock", menu)
            
            # Start tray icon in separate thread
            tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
            tray_thread.start()
            
            print("Tray icon setup successfully")
            
        except Exception as e:
            print(f"Tray icon setup failed: {e}")

class SettingsWindow:
    def __init__(self, parent):
        self.parent = parent
        self.settings = parent.settings
        
        self.window = tk.Toplevel(parent.root)
        self.window.title("SecClock Settings")
        self.window.geometry("500x650")  # Fixed height, no scrolling needed
        self.window.resizable(False, False)  # Not resizable
        
        # Set window icon
        try:
            if os.path.exists(ICON_PATH):
                self.window.iconbitmap(ICON_PATH)
        except:
            pass
        
        self.window.transient(parent.root)
        self.window.grab_set()
        
        # Apply ONLY background and foreground colors
        self.window.configure(bg=SETTINGS_BG)
        
        # Center the settings window on screen
        self.center_on_screen()
        
        self.create_widgets()
    
    def center_on_screen(self):
        """Center the window on the screen"""
        self.window.update_idletasks()
        
        # Get screen width and height
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        
        # Get window width and height
        window_width = self.window.winfo_width()
        window_height = self.window.winfo_height()
        
        # Calculate position
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # Set position
        self.window.geometry(f"+{x}+{y}")
    def create_widgets(self):
        # Main content frame with padding
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill="both", expand=True)

        # Window Size Section
        ttk.Label(main_frame, text="Window Size:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 10))
        
        # Size preset dropdown
        ttk.Label(main_frame, text="Size:").grid(row=1, column=0, sticky="w", pady=5)
        self.size_var = tk.StringVar(value=self.settings.get("window_size"))
        size_combo = ttk.Combobox(main_frame, textvariable=self.size_var, 
                                values=list(SIZE_PRESETS.keys()), 
                                state="readonly", width=15)
        size_combo.grid(row=1, column=1, sticky="w", pady=5)
        
        # Display current size
        current_size = SIZE_PRESETS[self.size_var.get()]
        size_label = ttk.Label(main_frame, text=f"Current: {current_size[0]}x{current_size[1]}", 
                            font=("Arial", 8), foreground="#888888")
        size_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 10))
        
        # Update size label when selection changes
        def update_size_label(*args):
            new_size = SIZE_PRESETS[self.size_var.get()]
            size_label.config(text=f"Current: {new_size[0]}x{new_size[1]}")
        self.size_var.trace('w', update_size_label)
        
        # Separator
        separator1 = ttk.Separator(main_frame, orient="horizontal")
        separator1.grid(row=3, column=0, columnspan=2, sticky="ew", pady=15)
        
        # Font Size
        ttk.Label(main_frame, text="Font Size:").grid(row=4, column=0, sticky="w", pady=5)
        self.font_size_var = tk.StringVar(value=str(self.settings.get("font_size")))
        font_size_spin = ttk.Spinbox(main_frame, from_=20, to=100, textvariable=self.font_size_var, width=10)
        font_size_spin.grid(row=4, column=1, sticky="w", pady=5)
        
        # Font Color
        ttk.Label(main_frame, text="Font Color:").grid(row=5, column=0, sticky="w", pady=5)
        self.font_color_var = tk.StringVar(value=self.settings.get("font_color"))
        color_frame = ttk.Frame(main_frame)
        color_frame.grid(row=5, column=1, sticky="w", pady=5)
        color_entry = ttk.Entry(color_frame, textvariable=self.font_color_var, width=10)
        color_entry.pack(side="left", padx=(0, 5))
        color_btn = ttk.Button(color_frame, text="Pick", command=self.pick_color)
        color_btn.pack(side="left")
        
        # Custom Background
        ttk.Label(main_frame, text="Custom Background:").grid(row=6, column=0, sticky="w", pady=5)
        bg_frame = ttk.Frame(main_frame)
        bg_frame.grid(row=6, column=1, sticky="w", pady=5)
        self.bg_path_var = tk.StringVar(value=self.settings.get("custom_bg_image"))
        bg_entry = ttk.Entry(bg_frame, textvariable=self.bg_path_var, width=20)
        bg_entry.pack(side="left", padx=(0, 5))
        ttk.Button(bg_frame, text="Browse", command=self.browse_image).pack(side="left")
        
        # Checkboxes
        self.remember_pos_var = tk.BooleanVar(value=self.settings.get("remember_position"))
        ttk.Checkbutton(main_frame, text="Remember window position", variable=self.remember_pos_var).grid(row=7, column=0, columnspan=2, sticky="w", pady=5)
        
        self.lock_drag_var = tk.BooleanVar(value=self.settings.get("lock_dragging"))
        ttk.Checkbutton(main_frame, text="Lock window dragging", variable=self.lock_drag_var).grid(row=8, column=0, columnspan=2, sticky="w", pady=5)
        
        self.run_startup_var = tk.BooleanVar(value=self.settings.get("run_on_startup"))
        ttk.Checkbutton(main_frame, text="Run on system startup", variable=self.run_startup_var).grid(row=9, column=0, columnspan=2, sticky="w", pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=10, column=0, columnspan=2, pady=20)
        
        ttk.Button(btn_frame, text="Apply", command=self.apply_settings).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="OK", command=self.ok_settings).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.window.destroy).pack(side="left", padx=5)
        
        # Separator
        separator2 = ttk.Separator(main_frame, orient="horizontal")
        separator2.grid(row=11, column=0, columnspan=2, sticky="ew", pady=20)
        
        # Author Section
        author_frame = ttk.Frame(main_frame)
        author_frame.grid(row=12, column=0, columnspan=2, pady=10)
        
        # Made with love text
        author_label = ttk.Label(
            author_frame, 
            text="Made with love By VeeJay", 
            font=("Arial", 10, "italic"),
            foreground="#aaaaaa"
        )
        author_label.pack(pady=(0, 15))
        
        # Social Media Buttons
        social_frame = ttk.Frame(author_frame)
        social_frame.pack()
        
        # Load and resize social media icons
        social_buttons = [
            ("discord", "Discord"),
            ("instagram", "Instagram"),
            ("youtube", "YouTube"), 
            ("github", "GitHub")
        ]
        
        self.social_icons = {}
        for platform, tooltip in social_buttons:
            try:
                # Load and resize icon to 80x80
                icon_img = Image.open(SOCIAL_ICONS[platform])
                icon_img = icon_img.resize((80, 80), Image.LANCZOS)
                self.social_icons[platform] = ImageTk.PhotoImage(icon_img)
                
                # Using default button style
                btn = tk.Button(
                    social_frame,
                    image=self.social_icons[platform],
                    command=lambda p=platform: self.open_social_link(p),
                    relief="flat",
                    borderwidth=1,
                    cursor="hand2",
                    width=82,
                    height=82
                )
                btn.pack(side="left", padx=8)
                
                # Add tooltip
                self.create_tooltip(btn, tooltip)
                
            except Exception as e:
                print(f"Error loading {platform} icon: {e}")
                # Fallback to text button if icon fails to load
                btn = tk.Button(
                    social_frame,
                    text=platform[:3].upper(),
                    command=lambda p=platform: self.open_social_link(p),
                    relief="flat",
                    borderwidth=1,
                    cursor="hand2",
                    font=("Arial", 8),
                    width=10,
                    height=4
                )
                btn.pack(side="left", padx=5)
                self.create_tooltip(btn, tooltip)      
        
    def create_tooltip(self, widget, text):
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            tooltip.configure(bg=SETTINGS_BG)
            label = ttk.Label(tooltip, text=text, 
                            background=SETTINGS_BG, 
                            foreground=SETTINGS_FG,
                            relief="solid", 
                            borderwidth=1,
                            padding=(5, 2))
            label.pack()
            widget.tooltip = tooltip
        
        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
        
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)
    
    def open_social_link(self, platform):
        link = SOCIAL_LINKS.get(platform)
        if link and link != f"https://{platform}.com/your-link":
            webbrowser.open(link)
        else:
            messagebox.showinfo("Social Media", f"{platform.capitalize()} link not configured yet!")
    
    def pick_color(self):
        from tkinter import colorchooser
        color = colorchooser.askcolor(initialcolor=self.font_color_var.get())[1]
        if color:
            self.font_color_var.set(color)
    
    def browse_image(self):
        filename = filedialog.askopenfilename(
            title="Select Background Image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.gif")]
        )
        if filename:
            self.bg_path_var.set(filename)
    
    def apply_settings(self):
        try:
            # Get new window size preset
            new_size_preset = self.size_var.get()
            if new_size_preset not in SIZE_PRESETS:
                messagebox.showerror("Error", "Invalid window size selected")
                return
            
            # Save settings
            self.settings.set("window_size", new_size_preset)
            self.settings.set("font_size", int(self.font_size_var.get()))
            self.settings.set("font_color", self.font_color_var.get())
            self.settings.set("custom_bg_image", self.bg_path_var.get())
            self.settings.set("remember_position", self.remember_pos_var.get())
            self.settings.set("lock_dragging", self.lock_drag_var.get())
            self.settings.set("run_on_startup", self.run_startup_var.get())
            
            # Update startup registry
            self.update_startup_registry()
            
            # Update parent window size and reload everything
            new_size = SIZE_PRESETS[new_size_preset]
            self.parent.SIZE = new_size
            self.parent.current_size_preset = new_size_preset
            x = self.parent.root.winfo_x()
            y = self.parent.root.winfo_y()
            self.parent.root.geometry(f"{new_size[0]}x{new_size[1]}+{x}+{y}")
            
            # Reload parent with new settings
            self.parent.load_custom_font()
            self.parent.load_custom_background()
            
            # Clear canvas and resize
            self.parent.canvas.delete("all")
            self.parent.canvas.config(width=new_size[0], height=new_size[1])
            
            # Force reload background with new size
            self.parent.load_current_background()
            
            # Recreate clock
            self.parent._create_separated_clock()
            
            # Update button positions
            self.parent.settings_btn.place(x=10, y=10, width=25, height=25)
            self.parent.close_btn.place(x=new_size[0]-35, y=10, width=25, height=25)
            self.parent.bg_btn.place(x=new_size[0]-70, y=10, width=25, height=25)
            
            # Update dragging
            if self.settings.get("lock_dragging"):
                self.parent.canvas.unbind("<Button-1>")
                self.parent.canvas.unbind("<B1-Motion>")
            else:
                self.parent._drag_dx = 0
                self.parent._drag_dy = 0
                self.parent.canvas.bind("<Button-1>", self.parent._start_drag)
                self.parent.canvas.bind("<B1-Motion>", self.parent._on_drag)
                
            messagebox.showinfo("Success", "Settings applied successfully!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply settings: {e}")

    def ok_settings(self):
        self.apply_settings()
        self.window.destroy()

    def update_startup_registry(self):
        try:
            app_path = sys.executable
            script_path = os.path.join(BASE_DIR, "main.py")
            full_command = f'"{app_path}" "{script_path}"'
            
            key = win32api.RegOpenKeyEx(
                win32con.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, win32con.KEY_SET_VALUE
            )
            
            if self.run_startup_var.get():
                win32api.RegSetValueEx(key, "SecClock", 0, win32con.REG_SZ, full_command)
            else:
                try:
                    win32api.RegDeleteValue(key, "SecClock")
                except:
                    pass
            
            win32api.RegCloseKey(key)
        except Exception as e:
            print(f"Startup registry error: {e}")

if __name__ == "__main__":
    # Create necessary directories
    os.makedirs(os.path.join(BASE_DIR, "assets"), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "fonts"), exist_ok=True)
    
    print("Starting SecClock...")
    print(f"Base directory: {BASE_DIR}")
    print(f"Font path: {FONT_PATH}")
    print(f"Icon path: {ICON_PATH}")
    print("Mask paths:")
    for size, path in MASK_PATHS.items():
        print(f"  {size}: {path}")
    
    app = SecClock()
    print("SecClock started successfully!")
    app.root.mainloop()