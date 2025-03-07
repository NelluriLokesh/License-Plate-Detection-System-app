import cv2
import imutils
import pytesseract
import winsound
import mysql.connector
import re
from tkinter import *
from tkinter import filedialog, messagebox, ttk, simpledialog
from PIL import Image, ImageTk
import threading
import time
from datetime import date
import numpy as np
import os
import json


pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

class LicensePlateDetector:
    def __init__(self, root):
        self.root = root
        self.root.title("License Plate Detection System")
        self.root.geometry("1700x900")  
        
        self.db = None
        self.cursor = None
        self.playing = False
        self.current_frame = None
        self.cap = None
        self.detected_plate = None
        self.complaint_window = None
        self.total_frames = 0
        self.current_time = "00:00"
        self.total_time = "00:00"
        
        self.style = ttk.Style()
        self.style.configure('Action.TButton', font=('Arial', 10, 'bold'), padding=5)
        self.style.configure('Regular.TButton', font=('Arial', 10), padding=5)
        
        # Create status indicator canvas with larger size
        self.db_status_canvas = Canvas(root, width=20, height=20, bg=self.root['bg'], highlightthickness=0)
        self.db_status_indicator = self.db_status_canvas.create_oval(4, 4, 16, 16, fill='red', outline='black')
        
        # Create all GUI elements first
        self.create_gui()
        
        # Then initialize database - this way all buttons exist before we try to enable/disable them
        self.init_database()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.last_back_click = 0
        self.last_forward_click = 0
        self.back_click_count = 0
        self.forward_click_count = 0
        self.playback_speed = 1.0  
        
    def create_gui(self):
        title_frame = Frame(self.root)
        title_frame.pack(side=TOP, fill=X)
        title_label = Label(title_frame, text="Traffic Management System", 
                          font=('Arial', 16, 'bold'))
        title_label.pack(expand=True, pady=5)  

        config_frame = Frame(self.root)
        config_frame.pack(fill=X, padx=10, pady=2)  
        
        # Database config button and status indicator
        db_container = Frame(config_frame)
        db_container.pack(side=LEFT)
        
        self.db_config_btn = ttk.Button(db_container, text="Database Settings",
                                      command=self.change_db_config,
                                      style='Regular.TButton', width=20)
        self.db_config_btn.pack(side=LEFT, padx=5)
        
        # Pack the status indicator canvas
        self.db_status_canvas = Canvas(db_container, width=20, height=20, bg=self.root['bg'], highlightthickness=0)
        self.db_status_indicator = self.db_status_canvas.create_oval(4, 4, 16, 16, fill='red', outline='black')
        self.db_status_canvas.pack(side=LEFT, padx=(0, 10))
        
        # Photos path config button
        self.path_config_btn = ttk.Button(config_frame, text="Change Photos Path",
                                        command=self.change_photos_path,
                                        style='Regular.TButton', width=20)
        self.path_config_btn.pack(side=LEFT, padx=5)
        
        # Create main frames
        self.main_frame = Frame(self.root)
        self.main_frame.pack(expand=True, fill=BOTH, padx=10, pady=2)  
        
        # Video frame (left side)
        self.video_frame = Frame(self.main_frame, width=850, height=650, bg='black')
        self.video_frame.pack(side=LEFT, padx=5, pady=2)  
        self.video_frame.pack_propagate(False)
        
        # Video display label
        self.video_label = Label(self.video_frame, bg='black')
        self.video_label.pack(expand=True, fill=BOTH)
        
        # Control frame (right side)
        self.control_frame = Frame(self.main_frame, width=600)  
        self.control_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=5, pady=2) 
        self.control_frame.pack_propagate(False)  
        
        # Control buttons with increased width
        self.btn_frame = Frame(self.control_frame)
        self.btn_frame.pack(pady=2, fill=X) 
        
        self.select_btn = ttk.Button(self.btn_frame, text="Select Video", 
                               command=self.select_video, width=25,  # Increased button width
                               style='Regular.TButton')
        self.select_btn.pack(pady=1)  
        
        # Navigation buttons frame
        self.nav_frame = Frame(self.control_frame)
        self.nav_frame.pack(pady=2) 
        
        # Time display
        self.time_label = Label(self.nav_frame, text="00:00 / 00:00",
                              font=('Arial', 10))
        self.time_label.pack(side=TOP, pady=1)  
        
        # Progress bar
        self.progress_var = DoubleVar()
        self.progress_bar = ttk.Scale(self.nav_frame, from_=0, to=100,
                                    orient=HORIZONTAL, length=200,
                                    variable=self.progress_var,
                                    command=self.seek_video)
        self.progress_bar.pack(side=TOP, pady=1, fill=X)  
        
        # Video controls frame
        self.video_controls = Frame(self.nav_frame)
        self.video_controls.pack(side=TOP, pady=1)  
        
        # Back button
        self.back_btn = ttk.Button(self.video_controls, text="⏪", 
                                command=self.back_video, width=8,
                                style='Regular.TButton')
        self.back_btn.pack(side=LEFT, padx=2)
        
        # Play button
        self.play_btn = ttk.Button(self.video_controls, text="Play", 
                             command=self.toggle_play, width=8,
                             style='Regular.TButton')
        self.play_btn.pack(side=LEFT, padx=2)
        
        # Forward button
        self.forward_btn = ttk.Button(self.video_controls, text="⏩", 
                                   command=self.forward_video, width=8,
                                   style='Regular.TButton')
        self.forward_btn.pack(side=LEFT, padx=2)
        
        # Speed label
        self.speed_label = Label(self.video_controls, text="1.0x",
                               font=('Arial', 10))
        self.speed_label.pack(side=LEFT, padx=5)
        
        self.detect_btn = ttk.Button(self.control_frame, text="Detect Plate", 
                               command=self.detect_current_frame, width=20,
                               style='Regular.TButton')
        self.detect_btn.pack(pady=2)  
        
        # Results frame with increased padding
        self.result_frame = ttk.LabelFrame(self.control_frame, text="Detection Results",
                                     padding=10) 
        self.result_frame.pack(fill=X, pady=2, padx=10)  
        
        # Create a frame for plate number and edit button
        self.plate_frame = Frame(self.result_frame)
        self.plate_frame.pack(fill=X, pady=1)  
        
        self.plate_label = Label(self.plate_frame, text="Plate Number:",
                               font=('Arial', 10))  
        self.plate_label.pack(side=LEFT, pady=1)  
        
        self.plate_value = Label(self.plate_frame, text="-",
                               font=('Arial', 10, 'bold'))  
        self.plate_value.pack(side=LEFT, pady=1, padx=3)  
        
        self.edit_plate_btn = ttk.Button(self.plate_frame, text="✎",
                                       command=self.edit_plate_number,
                                       width=3)
        self.edit_plate_btn.pack(side=LEFT, pady=1)  

        # Add copy button
        self.copy_plate_btn = ttk.Button(self.plate_frame, text="📋",
                                       command=self.copy_plate_number,
                                       width=3)
        self.copy_plate_btn.pack(side=LEFT, pady=1, padx=(2, 0))

        # Owner Details Frame
        self.owner_details_frame = ttk.LabelFrame(self.result_frame, text="Owner Details",
                                                padding=3)  
        self.owner_details_frame.pack(fill=X, pady=2)  

        # Owner Name
        self.owner_name_label = Label(self.owner_details_frame, text="Owner: -",
                                    font=('Arial', 10))  
        self.owner_name_label.pack(fill=X, pady=1)  

        # Phone Number
        self.phone_label = Label(self.owner_details_frame, text="Phone: -",
                               font=('Arial', 10))  
        self.phone_label.pack(fill=X, pady=1)  

        # Address
        self.address_label = Label(self.owner_details_frame, text="Address: -",
                                 font=('Arial', 10))  
        self.address_label.pack(fill=X, pady=1)  

        # Alert Frame
        self.alert_frame = Frame(self.result_frame, bg='white')
        self.alert_frame.pack(fill=X, pady=2)  
        
        self.alert_label = Label(self.alert_frame, text="",
                               font=('Arial', 10, 'bold'), bg='white')  
        self.alert_label.pack(pady=1)  # 
        
        self.status_value = Label(self.result_frame, text="Status: -",
                                font=('Arial', 10))  
        self.status_value.pack(pady=1)  
        
        # Add complaint count label
        self.complaint_count_label = Label(self.result_frame, text="Total Reports: 0",
                                font=('Arial', 10))  
        self.complaint_count_label.pack(pady=1)  
        
        # Add Click Image button
        self.click_image_btn = ttk.Button(self.result_frame, text="Click Image",
                                   command=self.save_current_frame,
                                   style='Action.TButton', width=15)
        self.click_image_btn.pack(pady=2)  
        
        # Add complaint statistics labels
        self.complaint_stats_frame = ttk.LabelFrame(self.result_frame, text="Statistics",
                                                  padding=3)  
        self.complaint_stats_frame.pack(fill=X, pady=2)  
        
        # Create two rows for statistics
        stats_row1 = Frame(self.complaint_stats_frame)
        stats_row1.pack(fill=X, padx=5, pady=2)
        
        stats_row2 = Frame(self.complaint_stats_frame)
        stats_row2.pack(fill=X, padx=5, pady=2)
        
        # Row 1: Total counts
        self.total_complaints_label = Label(stats_row1, text="Total: 0")
        self.total_complaints_label.pack(side=LEFT, padx=5)
        
        self.pending_complaints_label = Label(stats_row1, text="Active: 0")
        self.pending_complaints_label.pack(side=LEFT, padx=5)
        
        self.closed_complaints_label = Label(stats_row1, text="Closed: 0")
        self.closed_complaints_label.pack(side=LEFT, padx=5)
        
        # Row 2: Breakdown
        self.complaints_breakdown_label = Label(stats_row2, text="Complaints: 0")
        self.complaints_breakdown_label.pack(side=LEFT, padx=5)
        
        self.wanted_breakdown_label = Label(stats_row2, text="Wanted: 0")
        self.wanted_breakdown_label.pack(side=LEFT, padx=5)
        
        # Action Buttons Frame with better spacing
        self.action_frame = Frame(self.result_frame)
        self.action_frame.pack(fill=X, pady=5)  
        
        # Create frames for each row of buttons with more space
        self.action_buttons_row1 = Frame(self.action_frame)
        self.action_buttons_row1.pack(fill=X, pady=2)  
        
        self.action_buttons_row2 = Frame(self.action_frame)
        self.action_buttons_row2.pack(fill=X, pady=2)  

        self.action_buttons_row3 = Frame(self.action_frame)
        self.action_buttons_row3.pack(fill=X, pady=2)  
        
        # Row 1: Register Vehicle and File Complaint
        self.register_vehicle_btn = ttk.Button(self.action_buttons_row1, text="Register Vehicle",
                                       command=self.show_registration_form,
                                       style='Action.TButton', 
                                       width=20)  
        self.register_vehicle_btn.pack(side=LEFT, padx=5, expand=True)

        self.file_complaint_btn = ttk.Button(self.action_buttons_row1, text="File Complaint",
                                       command=self.show_complaint_form,
                                       style='Action.TButton', 
                                       width=20)  
        self.file_complaint_btn.pack(side=LEFT, padx=5, expand=True)

        # Row 2: View Complaints and Edit Complaints
        self.view_complaints_btn = ttk.Button(self.action_buttons_row2, text="View Complaints",
                                       command=self.show_complaints,
                                       style='Action.TButton', 
                                       width=20)  
        self.view_complaints_btn.pack(side=LEFT, padx=5, expand=True)

        self.edit_complaints_btn = ttk.Button(self.action_buttons_row2, text="Edit Complaints",
                                       command=self.edit_complaints,
                                       style='Action.TButton', 
                                       width=20)  
        self.edit_complaints_btn.pack(side=LEFT, padx=5, expand=True)

        # Row 3: Report Unknown and Update Wanted Status (side by side)
        frame_center = Frame(self.action_buttons_row3)
        frame_center.pack(expand=True)
        
        self.report_btn = ttk.Button(frame_center, text="Report",
                                      command=self.show_report_form,
                                      style='Action.TButton',
                                      width=20)  
        self.report_btn.pack(side=LEFT, padx=5)

        self.update_wanted_status_btn = ttk.Button(frame_center, text="Update Wanted Status",
                                      command=self.update_wanted_status,
                                      style='Action.TButton', 
                                      width=20)  
        self.update_wanted_status_btn.pack(side=LEFT, padx=5)
        
        # Bind keyboard shortcuts
        self.root.bind('<space>', lambda e: self.toggle_play())
        self.root.bind('<Left>', lambda e: self.back_video())
        self.root.bind('<Right>', lambda e: self.forward_video())
        self.root.bind('<Up>', lambda e: self.change_speed(0.5))
        self.root.bind('<Down>', lambda e: self.change_speed(-0.5))
        
    def init_database(self):
        """Initialize database connection and update status indicator"""
        try:
            # Read database configuration from app_config.json
            config_path = os.path.join(os.path.dirname(__file__), 'app_config.json')
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            if self.db is None:
                self.db = mysql.connector.connect(
                    host=config['database']['host'],
                    user=config['database']['user'],
                    password=config['database']['password'],
                    database=config['database']['database']
                )
                self.cursor = self.db.cursor(buffered=True)
                # Set indicator to green on successful connection
                self.db_status_canvas.itemconfig(self.db_status_indicator, fill='#00ff00')
                # Create tables if they don't exist
                self.create_tables()
                # Enable all buttons
                self.enable_all_buttons()
                
        except (json.JSONDecodeError, FileNotFoundError, mysql.connector.Error) as err:
            # Set indicator to red on any error
            self.db_status_canvas.itemconfig(self.db_status_indicator, fill='#ff0000')
            # Disable all buttons except database settings
            self.disable_all_buttons_except_db()
            
            if isinstance(err, json.JSONDecodeError):
                messagebox.showerror("Configuration Error", f"Error reading config file: {err}")
            elif isinstance(err, FileNotFoundError):
                messagebox.showerror("Configuration Error", "app_config.json not found")
            else:
                messagebox.showerror("Database Error", f"Could not connect to database: {err}")

    def enable_all_buttons(self):
        """Enable all buttons when database is connected"""
        try:
            # Enable all buttons except database settings
            self.select_btn.config(state='normal')
            self.detect_btn.config(state='normal')
            self.register_vehicle_btn.config(state='normal')
            self.file_complaint_btn.config(state='normal')
            self.view_complaints_btn.config(state='normal')
            self.edit_complaints_btn.config(state='normal')
            self.report_btn.config(state='normal')
            self.update_wanted_status_btn.config(state='normal')
            self.play_btn.config(state='normal')
            self.back_btn.config(state='normal')
            self.forward_btn.config(state='normal')
            self.path_config_btn.config(state='normal')
            
            if hasattr(self, 'edit_plate_btn'):
                self.edit_plate_btn.config(state='normal')
            if hasattr(self, 'copy_plate_btn'):
                self.copy_plate_btn.config(state='normal')
            if hasattr(self, 'click_image_btn'):
                self.click_image_btn.config(state='normal')
            
        except Exception as e:
            print(f"Error enabling buttons: {str(e)}")

    def disable_all_buttons_except_db(self):
        """Disable all buttons except database settings when database is not connected"""
        try:
            # Disable all buttons except database settings
            self.select_btn.config(state='disabled')
            self.detect_btn.config(state='disabled')
            self.register_vehicle_btn.config(state='disabled')
            self.file_complaint_btn.config(state='disabled')
            self.view_complaints_btn.config(state='disabled')
            self.edit_complaints_btn.config(state='disabled')
            self.report_btn.config(state='disabled')
            self.update_wanted_status_btn.config(state='disabled')
            self.play_btn.config(state='disabled')
            self.back_btn.config(state='disabled')
            self.forward_btn.config(state='disabled')
            self.path_config_btn.config(state='disabled')
            
            if hasattr(self, 'edit_plate_btn'):
                self.edit_plate_btn.config(state='disabled')
            if hasattr(self, 'copy_plate_btn'):
                self.copy_plate_btn.config(state='disabled')
            if hasattr(self, 'click_image_btn'):
                self.click_image_btn.config(state='disabled')
            
        except Exception as e:
            print(f"Error disabling buttons: {str(e)}")
        
    def create_tables(self):
        """Create necessary database tables"""
        try:
            # Create number_registering table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS number_registering (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    vehicle_number VARCHAR(20) NOT NULL UNIQUE,
                    owner_name VARCHAR(100) NOT NULL,
                    vehicle_type VARCHAR(50),
                    registration_date DATE,
                    phone_number VARCHAR(15),
                    address TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create complaints table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS complaints (
                    complaint_id INT AUTO_INCREMENT PRIMARY KEY,
                    vehicle_number VARCHAR(20) NOT NULL,
                    complaint_type VARCHAR(100) NOT NULL,
                    description TEXT,
                    location VARCHAR(200),
                    incident_date DATE,
                    status ENUM('Pending', 'In Progress', 'Resolved', 'Closed') DEFAULT 'Pending',
                    fine_amount DECIMAL(10,2) DEFAULT 0.00,
                    reported_by VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (vehicle_number) REFERENCES number_registering(vehicle_number) ON DELETE CASCADE
                )
            """)
            
            # Create wanted_list table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS wanted_list (
                    wanted_id INT AUTO_INCREMENT PRIMARY KEY,
                    vehicle_number VARCHAR(20) NOT NULL,
                    incident_type VARCHAR(100) NOT NULL,
                    description TEXT,
                    location VARCHAR(200),
                    incident_date DATE,
                    status ENUM('Active', 'Resolved', 'False Alarm') DEFAULT 'Active',
                    severity_level ENUM('Low', 'Medium', 'High') DEFAULT 'Medium',
                    reported_by VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.db.commit()
        except mysql.connector.Error as err:
            messagebox.showerror("Database Error", f"Could not create tables: {err}")
            self.root.destroy()

    def change_db_config(self):
        """Handle database configuration changes"""
        try:
            prev_config = {}
            if os.path.exists('app_config.json'):
                with open('app_config.json', 'r') as f:
                    config = json.load(f)
                    prev_config = config.get('database', {})

            # Create dialog for database configuration
            dialog = DatabaseConfigDialog(self.root, prev_config)
            if dialog.result:
                try:
                    # Test connection with new configuration
                    new_db = mysql.connector.connect(**dialog.result)
                    new_db.close()
                    
                    # Update app_config.json with new database settings
                    if os.path.exists('app_config.json'):
                        with open('app_config.json', 'r') as f:
                            config = json.load(f)
                    else:
                        config = {}
                    
                    config['database'] = dialog.result
                    
                    with open('app_config.json', 'w') as f:
                        json.dump(config, f, indent=4)
                    
                    # Close existing connection if any
                    if self.db:
                        try:
                            self.db.close()
                        except:
                            pass
                        self.db = None
                        self.cursor = None
                    
                    # Reinitialize database connection
                    self.init_database()
                    messagebox.showinfo("Success", "Database configuration updated successfully!")
                except mysql.connector.Error as e:
                    messagebox.showerror("Connection Error", f"Failed to connect to database: {str(e)}")
                    self.db_status_canvas.itemconfig(self.db_status_indicator, fill='#ff0000')
                    self.disable_all_buttons_except_db()
        except Exception as e:
            print(f"Error in change_db_config: {str(e)}")
            messagebox.showerror("Error", "Failed to update database configuration")
            self.db_status_canvas.itemconfig(self.db_status_indicator, fill='#ff0000')
            self.disable_all_buttons_except_db()

    def on_closing(self):
        """Handle application cleanup when window is closed"""
        try:
            # Close video capture if open
            if self.cap and self.cap.isOpened():
                self.cap.release()
            
            # Close database connections
            if self.cursor:
                self.cursor.close()
                self.cursor = None
            if self.db:
                self.db.close()
                self.db = None
                
        except Exception as e:
            print(f"Error during cleanup: {e}")
        finally:
            self.root.destroy()

    def __del__(self):
        """Backup cleanup method"""
        try:
            if hasattr(self, 'cap') and self.cap and self.cap.isOpened():
                self.cap.release()
            if hasattr(self, 'cursor') and self.cursor:
                self.cursor.close()
            if hasattr(self, 'db') and self.db:
                self.db.close()
        except:
            pass  

    def show_complaint_form(self):
        if not self.detected_plate:
            messagebox.showerror("Error", "Please detect a license plate first")
            return
            
        # Check if vehicle is registered first
        try:
            self.cursor.execute("SELECT vehicle_number FROM number_registering WHERE vehicle_number = %s", 
                              (self.detected_plate,))
            if not self.cursor.fetchone():
                messagebox.showerror("Error", "Vehicle must be registered before filing a complaint.\nPlease register the vehicle first.")
                return
        except mysql.connector.Error as err:
            messagebox.showerror("Database Error", f"Error checking vehicle registration: {err}")
            return
            
        if self.complaint_window is not None:
            self.complaint_window.destroy()
        
        self.complaint_window = Toplevel(self.root)
        self.complaint_window.title("File Complaint")
        self.complaint_window.geometry("400x600")
        
        # Complaint Form
        complaint_frame = ttk.LabelFrame(self.complaint_window, text="Complaint Details",
                                   padding=10)
        complaint_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        # Complaint Type
        ttk.Label(complaint_frame, text="Complaint Type:").pack(pady=2)
        complaint_type_var = StringVar(value="Traffic Violation")
        complaint_type_menu = ttk.OptionMenu(complaint_frame, complaint_type_var,
                                           "Traffic Violation",
                                           "Speeding",
                                           "Reckless Driving",
                                           "Parking Violation",
                                           "Signal Jump",
                                           "Other")
        complaint_type_menu.pack(pady=2, fill=X)
        
        # Description
        ttk.Label(complaint_frame, text="Description:").pack(pady=2)
        description_text = Text(complaint_frame, height=4)
        description_text.pack(pady=2, fill=X)
        
        # Location
        ttk.Label(complaint_frame, text="Location:").pack(pady=2)
        location_entry = ttk.Entry(complaint_frame)
        location_entry.pack(pady=2, fill=X)
        
        # Incident Date
        ttk.Label(complaint_frame, text="Incident Date:").pack(pady=2)
        incident_date_entry = ttk.Entry(complaint_frame)
        incident_date_entry.insert(0, date.today().strftime('%Y-%m-%d'))
        incident_date_entry.pack(pady=2, fill=X)
        
        # Fine Amount
        ttk.Label(complaint_frame, text="Fine Amount:").pack(pady=2)
        fine_amount_entry = ttk.Entry(complaint_frame)
        fine_amount_entry.insert(0, "0.00")
        fine_amount_entry.pack(pady=2, fill=X)
        
        # Reported By
        ttk.Label(complaint_frame, text="Reported By:").pack(pady=2)
        reported_by_entry = ttk.Entry(complaint_frame)
        reported_by_entry.pack(pady=2, fill=X)
        
        def submit_complaint():
            try:
                # Insert complaint
                self.cursor.execute("""
                    INSERT INTO complaints 
                    (vehicle_number, complaint_type, description, location, 
                     incident_date, fine_amount, reported_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    self.detected_plate,
                    complaint_type_var.get(),
                    description_text.get("1.0", END).strip(),
                    location_entry.get().strip(),
                    incident_date_entry.get().strip(),
                    float(fine_amount_entry.get().strip() or 0),
                    reported_by_entry.get().strip()
                ))
                
                self.db.commit()
                self.update_stats_for_plate(self.detected_plate)
                self.complaint_window.destroy()
                
            except mysql.connector.Error as err:
                messagebox.showerror("Database Error", f"Error filing complaint: {err}")
                self.db.rollback()
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid fine amount")
        
        ttk.Button(complaint_frame, text="Submit Complaint",
                  command=submit_complaint).pack(pady=10)

    def select_video(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Video files", "*.mp4 *.avi *.mkv"), ("All files", "*.*")])
        if file_path:
            if self.cap is not None:
                self.cap.release()
            
            self.cap = cv2.VideoCapture(file_path)
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            # Calculate total duration
            total_seconds = self.total_frames / fps
            minutes = int(total_seconds // 60)
            seconds = int(total_seconds % 60)
            self.total_time = f"{minutes:02d}:{seconds:02d}"
            
            self.playing = False
            self.play_btn.config(text="Play")
            self.playback_speed = 1.0
            self.speed_label.config(text="1.0x")
            self.progress_var.set(0)
            self.update_time_display(0)
            
            ret, frame = self.cap.read()
            if ret:
                self.current_frame = frame
                frame = imutils.resize(frame, width=980)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.imgtk = imgtk
                self.video_label.configure(image=imgtk)
                self.status_value.config(text="Ready to play")

    def update_time_display(self, current_frame):
        if self.cap is not None:
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            current_seconds = current_frame / fps
            minutes = int(current_seconds // 60)
            seconds = int(current_seconds % 60)
            self.current_time = f"{minutes:02d}:{seconds:02d}"
            self.time_label.config(text=f"{self.current_time} / {self.total_time}")
            
            # Update progress bar
            if self.total_frames > 0:
                progress = (current_frame / self.total_frames) * 100
                self.progress_var.set(progress)

    def seek_video(self, value):
        if self.cap is not None:
            # Convert progress percentage to frame number
            frame_pos = int((float(value) / 100) * self.total_frames)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
            
            # Update time display
            self.update_time_display(frame_pos)
            
            # If paused, show the current frame
            if not self.playing:
                ret, frame = self.cap.read()
                if ret:
                    self.current_frame = frame
                    frame = imutils.resize(frame, width=980)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame)
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.video_label.imgtk = imgtk
                    self.video_label.configure(image=imgtk)

    def change_speed(self, delta):
        if self.cap is not None:
            self.playback_speed = max(0.5, min(4.0, self.playback_speed + delta))
            self.speed_label.config(text=f"{self.playback_speed:.1f}x")
            self.status_value.config(text=f"Playback speed: {self.playback_speed:.1f}x")

    def play_video(self):
        if self.playing and self.cap is not None:
            # Get current frame position
            current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            
            # Adjust frame reading based on playback speed
            for _ in range(int(self.playback_speed)):
                ret, frame = self.cap.read()
                if not ret:
                    self.playing = False
                    self.play_btn.config(text="Play")
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self.playback_speed = 1.0
                    self.speed_label.config(text="1.0x")
                    self.update_time_display(0)
                    return
                self.current_frame = frame
            
            # Update time display and progress bar
            self.update_time_display(current_frame)
            
            frame = imutils.resize(frame, width=980)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            imgtk = ImageTk.PhotoImage(image=img)
            self.video_label.imgtk = imgtk
            self.video_label.configure(image=imgtk)
            
            # Adjust delay based on playback speed
            self.root.after(int(10/self.playback_speed), self.play_video)

    def back_video(self):
        if self.cap is None:
            messagebox.showwarning("Warning", "Please select a video first!")
            return
            
        current_time = time.time()
        
        # Reset click count if last click was more than 0.5 second ago
        if current_time - self.last_back_click > 0.5:
            self.back_click_count = 0
        
        self.back_click_count += 1
        self.last_back_click = current_time
        
        if self.back_click_count == 1:
            # First click: Slow down playback
            self.change_speed(-0.5)
        else:
            # Multiple clicks: Skip backwards
            skip_time = 5 * (self.back_click_count - 1)  # 5 seconds for double click, 10 for triple
            
            # Get current frame position
            current_frame = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            # Calculate new position
            new_frame = max(0, current_frame - (skip_time * fps))
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
            
            # Update time display and status
            self.update_time_display(new_frame)
            self.status_value.config(text=f"Skipped back {skip_time} seconds")
            
            # If video is not playing, show the current frame
            if not self.playing:
                ret, frame = self.cap.read()
                if ret:
                    self.current_frame = frame
                    frame = imutils.resize(frame, width=980)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame)
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.video_label.imgtk = imgtk
                    self.video_label.configure(image=imgtk)

    def forward_video(self):
        if self.cap is None:
            messagebox.showwarning("Warning", "Please select a video first!")
            return
            
        current_time = time.time()
        
        # Reset click count if last click was more than 0.5 second ago
        if current_time - self.last_forward_click > 0.5:
            self.forward_click_count = 0
        
        self.forward_click_count += 1
        self.last_forward_click = current_time
        
        if self.forward_click_count == 1:
            # First click: Speed up playback
            self.change_speed(0.5)
        else:
            # Multiple clicks: Skip forward
            skip_time = 5 * (self.forward_click_count - 1)  # 5 seconds for double click, 10 for triple
            
            # Get current frame position and video properties
            current_frame = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            # Calculate new position
            new_frame = min(self.total_frames - 1, current_frame + (skip_time * fps))
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
            
            # Update time display and status
            self.update_time_display(new_frame)
            self.status_value.config(text=f"Skipped forward {skip_time} seconds")
            
            # If video is not playing, show the new frame
            if not self.playing:
                ret, frame = self.cap.read()
                if ret:
                    self.current_frame = frame
                    frame = imutils.resize(frame, width=980)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame)
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.video_label.imgtk = imgtk
                    self.video_label.configure(image=imgtk)

    def toggle_play(self):
        if self.cap is None:
            messagebox.showwarning("Warning", "Please select a video first!")
            return
        
        self.playing = not self.playing
        if self.playing:
            self.play_btn.config(text="Pause")
            self.playback_speed = 1.0  # Reset speed when playing/pausing
            self.play_video()
        else:
            self.play_btn.config(text="Play")

    def detect_current_frame(self):
        if self.current_frame is None:
            # Update status in plate_value instead of status_label
            self.plate_value.config(text="No frame available!")
            self.status_value.config(text="Please play the video first")
            return

        # Convert frame to grayscale
        gray = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2GRAY)
        bfilter = cv2.bilateralFilter(gray, 11, 17, 17)
        edged = cv2.Canny(bfilter, 30, 200)

        # Find contours
        keypoints = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours = imutils.grab_contours(keypoints)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

        location = None
        for contour in contours:
            approx = cv2.approxPolyDP(contour, 10, True)
            if len(approx) == 4:
                location = approx
                break

        if location is not None:
            mask = np.zeros(gray.shape, np.uint8)
            new_image = cv2.drawContours(mask, [location], 0, 255, -1)
            new_image = cv2.bitwise_and(self.current_frame, self.current_frame, mask=mask)

            (x, y) = np.where(mask == 255)
            (x1, y1) = (np.min(y), np.min(x))
            (x2, y2) = (np.max(y), np.max(x))
            cropped_image = gray[y1:y2+1, x1:x2+1]

            # Read plate number
            plate_text = pytesseract.image_to_string(cropped_image, config='--psm 11')
            plate_text = re.sub(r'[^A-Z0-9]', '', plate_text.upper())

            if plate_text:
                self.detected_plate = plate_text
                self.plate_value.config(text=plate_text)
                self.update_detection_results(plate_text)
                winsound.Beep(1000, 100)  # Beep sound on detection
            else:
                self.plate_value.config(text="Could not read plate text!")
                self.status_value.config(text="Detection failed")
        else:
            self.plate_value.config(text="No license plate found!")
            self.status_value.config(text="Detection failed")

    def update_detection_results(self, plate_number):
        """Update detection results including owner details and alerts"""
        if not plate_number:
            return
            
        self.plate_value.config(text=plate_number)
        
        try:
            # First check for wanted status regardless of registration
            self.cursor.execute("""
                SELECT COUNT(*), MAX(severity_level) 
                FROM wanted_list 
                WHERE vehicle_number = %s 
                AND status = 'Active'
            """, (plate_number,))
            
            wanted_result = self.cursor.fetchone()
            
            if wanted_result and wanted_result[0] > 0:
                severity = wanted_result[1]
                if severity == 'High':
                    self.alert_label.config(
                        text="⚠ HIGH ALERT: WANTED VEHICLE",
                        fg='white', bg='red'  # Changed text to white and background to red for better visibility
                    )
                    self.alert_frame.config(bg='red')  # Changed frame background to red for emphasis
                    # Play alert sound
                    winsound.Beep(1000, 500)  # Added sound alert for high priority
                elif severity == 'Medium':
                    self.alert_label.config(
                        text="⚠ ALERT: WANTED VEHICLE",
                        fg='black', bg='yellow'
                    )
                    self.alert_frame.config(bg='yellow')
                else:
                    self.alert_label.config(
                        text="⚠ Notice: Vehicle of Interest",
                        fg='black', bg='lightgray'
                    )
                    self.alert_frame.config(bg='lightgray')
            else:
                self.alert_label.config(text="")
                self.alert_frame.config(bg='white')
            
            # Get owner details
            self.cursor.execute("""
                SELECT owner_name, phone_number, address 
                FROM number_registering 
                WHERE vehicle_number = %s
            """, (plate_number,))
            owner_result = self.cursor.fetchone()
            
            if owner_result:
                self.owner_name_label.config(text=f"Owner: {owner_result[0]}")
                self.phone_label.config(text=f"Phone: {owner_result[1]}")
                self.address_label.config(text=f"Address: {owner_result[2]}")
                self.status_value.config(text="Status: Registered")
            else:
                # Reset owner details if vehicle not found
                self.owner_name_label.config(text="Owner: -")
                self.phone_label.config(text="Phone: -")
                self.address_label.config(text="Address: -")
                self.status_value.config(text="Status: Not Registered")
                
        except mysql.connector.Error as err:
            messagebox.showerror("Database Error", f"Error accessing database: {err}")
            
    def update_wanted_status(self):
        """Update the status of a wanted vehicle when found"""
        if not self.detected_plate:
            messagebox.showerror("Error", "No plate detected")
            return
            
        try:
            # Check if vehicle is in wanted list
            self.cursor.execute("""
                SELECT wanted_id, incident_type, severity_level 
                FROM wanted_list 
                WHERE vehicle_number = %s AND status = 'Active'
            """, (self.detected_plate,))
            
            wanted_record = self.cursor.fetchone()
            if not wanted_record:
                messagebox.showinfo("Info", "This vehicle is not in the active wanted list")
                return
                
            # Ask for confirmation with incident details
            wanted_id, incident_type, severity = wanted_record
            if messagebox.askyesno("Confirm Status Update", 
                                 f"Update status for vehicle {self.detected_plate}\n" +
                                 f"Incident: {incident_type}\n" +
                                 f"Severity: {severity}\n\n" +
                                 "Change status from 'Active' to 'Resolved'?"):
                
                # Update the status
                self.cursor.execute("""
                    UPDATE wanted_list 
                    SET status = 'Resolved' 
                    WHERE wanted_id = %s
                """, (wanted_id,))
                
                self.db.commit()
                messagebox.showinfo("Success", "Wanted vehicle status updated to Resolved")
                
                # Update the display
                self.update_detection_results(self.detected_plate)
                
        except mysql.connector.Error as err:
            messagebox.showerror("Database Error", f"Error updating wanted status: {err}")
            self.db.rollback()

    def show_report_form(self):
        """Show form to report a vehicle (known or unknown)"""
        if not self.detected_plate:
            messagebox.showerror("Error", "Please detect a license plate first")
            return
            
        report_window = Toplevel(self.root)
        report_window.title("Report Vehicle")
        report_window.geometry("400x500")
        
        # Create form fields
        form_frame = ttk.LabelFrame(report_window, text="Report Details", padding=10)
        form_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        # Incident Type
        ttk.Label(form_frame, text="Incident Type:").pack(pady=2)
        incident_type_var = StringVar(value="Traffic Violation")
        incident_type_menu = ttk.OptionMenu(form_frame, incident_type_var,
                                        "Traffic Violation",
                                        "Hit and Run",
                                        "Suspicious Activity",
                                        "Theft",
                                        "Other")
        incident_type_menu.pack(pady=2, fill=X)
        
        # Description
        ttk.Label(form_frame, text="Description:").pack(pady=2)
        description_text = Text(form_frame, height=4)
        description_text.pack(pady=2, fill=X)
        
        # Location
        ttk.Label(form_frame, text="Location:").pack(pady=2)
        location_entry = ttk.Entry(form_frame)
        location_entry.pack(pady=2, fill=X)
        
        # Incident Date
        ttk.Label(form_frame, text="Incident Date:").pack(pady=2)
        incident_date_entry = ttk.Entry(form_frame)
        incident_date_entry.insert(0, date.today().strftime('%Y-%m-%d'))
        incident_date_entry.pack(pady=2, fill=X)
        
        # Severity Level
        ttk.Label(form_frame, text="Severity Level:").pack(pady=2)
        severity_var = StringVar(value="Medium")
        severity_frame = Frame(form_frame)
        severity_frame.pack(fill=X, pady=2)
        
        ttk.Radiobutton(severity_frame, text="Low", 
                       variable=severity_var, value="Low").pack(side=LEFT, padx=20)
        ttk.Radiobutton(severity_frame, text="Medium", 
                       variable=severity_var, value="Medium").pack(side=LEFT, padx=20)
        ttk.Radiobutton(severity_frame, text="High", 
                       variable=severity_var, value="High").pack(side=LEFT, padx=20)
        
        # Reported By
        ttk.Label(form_frame, text="Reported By:").pack(pady=2)
        reported_by_entry = ttk.Entry(form_frame)
        reported_by_entry.pack(pady=2, fill=X)
        
        def submit_report():
            try:
                # Insert into wanted_list
                self.cursor.execute("""
                    INSERT INTO wanted_list 
                    (vehicle_number, incident_type, description, location, 
                     incident_date, severity_level, reported_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    self.detected_plate,
                    incident_type_var.get(),
                    description_text.get("1.0", END).strip(),
                    location_entry.get().strip(),
                    incident_date_entry.get().strip(),
                    severity_var.get(),
                    reported_by_entry.get().strip()
                ))
                
                self.db.commit()
                self.update_stats_for_plate(self.detected_plate)
                report_window.destroy()
                messagebox.showinfo("Success", "Report submitted successfully!")
                
            except mysql.connector.Error as err:
                messagebox.showerror("Database Error", f"Error submitting report: {err}")
                self.db.rollback()
        
        ttk.Button(form_frame, text="Submit Report",
                  command=submit_report,
                  style='Action.TButton').pack(pady=10)

    def show_registration_form(self):
        if not self.detected_plate:
            messagebox.showerror("Error", "Please detect a license plate first")
            return
            
        # Check if vehicle is already registered
        try:
            self.cursor.execute("SELECT vehicle_number FROM number_registering WHERE vehicle_number = %s", 
                              (self.detected_plate,))
            if self.cursor.fetchone():
                messagebox.showinfo("Info", "Vehicle is already registered")
                return
        except mysql.connector.Error as err:
            messagebox.showerror("Database Error", f"Error checking vehicle registration: {err}")
            return

        # Create registration window
        reg_window = Toplevel(self.root)
        reg_window.title("Vehicle Registration")
        reg_window.geometry("400x500")
        
        # Main frame
        main_frame = ttk.LabelFrame(reg_window, text="Vehicle Registration Details", padding=10)
        main_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        # Vehicle number (display only)
        ttk.Label(main_frame, text="Vehicle Number:", font=('Arial', 11, 'bold')).pack(pady=2)
        ttk.Label(main_frame, text=self.detected_plate, font=('Arial', 11)).pack(pady=2)
        
        # Owner name
        ttk.Label(main_frame, text="Owner Name:").pack(pady=2)
        owner_name_entry = ttk.Entry(main_frame)
        owner_name_entry.pack(pady=2, fill=X)
        
        # Vehicle type
        ttk.Label(main_frame, text="Vehicle Type:").pack(pady=2)
        vehicle_type_var = StringVar(value="Car")
        vehicle_type_menu = ttk.OptionMenu(main_frame, vehicle_type_var, 
                                         "Car", "Bike", "Truck", "Bus", "Other")
        vehicle_type_menu.pack(pady=2)
        
        # Phone number
        ttk.Label(main_frame, text="Phone Number:").pack(pady=2)
        phone_entry = ttk.Entry(main_frame)
        phone_entry.pack(pady=2, fill=X)
        
        # Address
        ttk.Label(main_frame, text="Address:").pack(pady=2)
        address_text = Text(main_frame, height=4)
        address_text.pack(pady=2, fill=X)
        
        def submit_registration():
            # Get values
            owner_name = owner_name_entry.get().strip()
            vehicle_type = vehicle_type_var.get()
            phone_number = phone_entry.get().strip()
            address = address_text.get("1.0", END).strip()
            
            # Validate
            if not all([owner_name, vehicle_type, phone_number, address]):
                messagebox.showerror("Error", "All fields are required")
                return
            
            try:
                # Insert registration
                self.cursor.execute("""
                    INSERT INTO number_registering 
                    (vehicle_number, owner_name, vehicle_type, registration_date, phone_number, address)
                    VALUES (%s, %s, %s, CURDATE(), %s, %s)
                """, (self.detected_plate, owner_name, vehicle_type, phone_number, address))
                
                self.db.commit()
                self.update_detection_results(self.detected_plate)
                reg_window.destroy()
                
            except mysql.connector.Error as err:
                messagebox.showerror("Database Error", f"Error registering vehicle: {err}")
                self.db.rollback()
        
        # Submit button
        ttk.Button(main_frame, text="Register", 
                  command=submit_registration,
                  style='Action.TButton').pack(pady=20)

    def back_video(self):
        if self.cap is None:
            messagebox.showwarning("Warning", "Please select a video first!")
            return
            
        current_time = time.time()
        
        # Reset click count if last click was more than 0.5 second ago
        if current_time - self.last_back_click > 0.5:
            self.back_click_count = 0
        
        self.back_click_count += 1
        self.last_back_click = current_time
        
        if self.back_click_count == 1:
            # First click: Slow down playback
            self.change_speed(-0.5)
        else:
            # Multiple clicks: Skip backwards
            skip_time = 5 * (self.back_click_count - 1)  # 5 seconds for double click, 10 for triple
            
            # Get current frame position
            current_frame = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            # Calculate new position
            new_frame = max(0, current_frame - (skip_time * fps))
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
            
            # Update time display and status
            self.update_time_display(new_frame)
            self.status_value.config(text=f"Skipped back {skip_time} seconds")
            
            # If video is not playing, show the current frame
            if not self.playing:
                ret, frame = self.cap.read()
                if ret:
                    self.current_frame = frame
                    frame = imutils.resize(frame, width=980)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame)
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.video_label.imgtk = imgtk
                    self.video_label.configure(image=imgtk)

    def forward_video(self):
        if self.cap is None:
            messagebox.showwarning("Warning", "Please select a video first!")
            return
            
        current_time = time.time()
        
        # Reset click count if last click was more than 0.5 second ago
        if current_time - self.last_forward_click > 0.5:
            self.forward_click_count = 0
        
        self.forward_click_count += 1
        self.last_forward_click = current_time
        
        if self.forward_click_count == 1:
            # First click: Speed up playback
            self.change_speed(0.5)
        else:
            # Multiple clicks: Skip forward
            skip_time = 5 * (self.forward_click_count - 1)  # 5 seconds for double click, 10 for triple
            
            # Get current frame position and video properties
            current_frame = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            # Calculate new position
            new_frame = min(self.total_frames - 1, current_frame + (skip_time * fps))
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
            
            # Update time display and status
            self.update_time_display(new_frame)
            self.status_value.config(text=f"Skipped forward {skip_time} seconds")
            
            # If video is not playing, show the new frame
            if not self.playing:
                ret, frame = self.cap.read()
                if ret:
                    self.current_frame = frame
                    frame = imutils.resize(frame, width=980)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame)
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.video_label.imgtk = imgtk
                    self.video_label.configure(image=imgtk)

    def toggle_play(self):
        if self.cap is None:
            messagebox.showwarning("Warning", "Please select a video first!")
            return
        
        self.playing = not self.playing
        if self.playing:
            self.play_btn.config(text="Pause")
            self.playback_speed = 1.0  # Reset speed when playing/pausing
            self.play_video()
        else:
            self.play_btn.config(text="Play")

    def detect_current_frame(self):
        if self.current_frame is None:
            # Update status in plate_value instead of status_label
            self.plate_value.config(text="No frame available!")
            self.status_value.config(text="Please play the video first")
            return

        # Convert frame to grayscale
        gray = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2GRAY)
        bfilter = cv2.bilateralFilter(gray, 11, 17, 17)
        edged = cv2.Canny(bfilter, 30, 200)

        # Find contours
        keypoints = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours = imutils.grab_contours(keypoints)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

        location = None
        for contour in contours:
            approx = cv2.approxPolyDP(contour, 10, True)
            if len(approx) == 4:
                location = approx
                break

        if location is not None:
            mask = np.zeros(gray.shape, np.uint8)
            new_image = cv2.drawContours(mask, [location], 0, 255, -1)
            new_image = cv2.bitwise_and(self.current_frame, self.current_frame, mask=mask)

            (x, y) = np.where(mask == 255)
            (x1, y1) = (np.min(y), np.min(x))
            (x2, y2) = (np.max(y), np.max(x))
            cropped_image = gray[y1:y2+1, x1:x2+1]

            # Read plate number
            plate_text = pytesseract.image_to_string(cropped_image, config='--psm 11')
            plate_text = re.sub(r'[^A-Z0-9]', '', plate_text.upper())

            if plate_text:
                self.detected_plate = plate_text
                self.plate_value.config(text=plate_text)
                self.update_detection_results(plate_text)
                winsound.Beep(1000, 100)  # Beep sound on detection
            else:
                self.plate_value.config(text="Could not read plate text!")
                self.status_value.config(text="Detection failed")
        else:
            self.plate_value.config(text="No license plate found!")
            self.status_value.config(text="Detection failed")

    def update_stats_for_plate(self, plate_number):
        try:
            if not plate_number:
                # Clear all statistics
                self.total_complaints_label.config(text="Total: 0")
                self.pending_complaints_label.config(text="Active: 0")
                self.closed_complaints_label.config(text="Closed: 0")
                self.complaints_breakdown_label.config(text="Complaints: 0")
                self.wanted_breakdown_label.config(text="Wanted: 0")
                self.complaint_count_label.config(text="Total Reports: 0")
                return

            # Count complaints and their statuses for this plate
            self.cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status IN ('Pending', 'In Progress') THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN status IN ('Closed', 'Resolved') THEN 1 ELSE 0 END) as closed
                FROM complaints
                WHERE vehicle_number = %s
            """, (plate_number,))
            complaints_stats = self.cursor.fetchone()
            total_complaints = complaints_stats[0] or 0
            active_complaints = complaints_stats[1] or 0
            closed_complaints = complaints_stats[2] or 0

            # Count wanted reports and their statuses for this plate
            self.cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN status IN ('Resolved', 'False Alarm') THEN 1 ELSE 0 END) as closed
                FROM wanted_list
                WHERE vehicle_number = %s
            """, (plate_number,))
            wanted_stats = self.cursor.fetchone()
            total_wanted = wanted_stats[0] or 0
            active_wanted = wanted_stats[1] or 0
            closed_wanted = wanted_stats[2] or 0

            # Update all statistics labels
            total = total_complaints + total_wanted
            active = active_complaints + active_wanted
            closed = closed_complaints + closed_wanted

            self.total_complaints_label.config(text=f"Total: {total}")
            self.pending_complaints_label.config(text=f"Active: {active}")
            self.closed_complaints_label.config(text=f"Closed: {closed}")
            self.complaints_breakdown_label.config(text=f"Complaints: {total_complaints}")
            self.wanted_breakdown_label.config(text=f"Wanted: {total_wanted}")
            self.complaint_count_label.config(text=f"Total Reports: {total}")

        except mysql.connector.Error as err:
            print(f"Error updating statistics for plate {plate_number}: {err}")

    def update_wanted_status(self):
        """Update the status of a wanted vehicle when found"""
        if not self.detected_plate:
            messagebox.showerror("Error", "No plate detected")
            return
            
        try:
            # Check if vehicle is in wanted list
            self.cursor.execute("""
                SELECT wanted_id, incident_type, severity_level 
                FROM wanted_list 
                WHERE vehicle_number = %s AND status = 'Active'
            """, (self.detected_plate,))
            
            wanted_record = self.cursor.fetchone()
            if not wanted_record:
                messagebox.showinfo("Info", "This vehicle is not in the active wanted list")
                return
                
            # Ask for confirmation with incident details
            wanted_id, incident_type, severity = wanted_record
            if messagebox.askyesno("Confirm Status Update", 
                                 f"Update status for vehicle {self.detected_plate}\n" +
                                 f"Incident: {incident_type}\n" +
                                 f"Severity: {severity}\n\n" +
                                 "Change status from 'Active' to 'Resolved'?"):
                
                # Update the status
                self.cursor.execute("""
                    UPDATE wanted_list 
                    SET status = 'Resolved' 
                    WHERE wanted_id = %s
                """, (wanted_id,))
                
                self.db.commit()
                messagebox.showinfo("Success", "Wanted vehicle status updated to Resolved")
                
                # Update the display
                self.update_detection_results(self.detected_plate)
                
        except mysql.connector.Error as err:
            messagebox.showerror("Database Error", f"Error updating wanted status: {err}")
            self.db.rollback()

    def show_report_form(self):
        """Show form to report a vehicle (known or unknown)"""
        if not self.detected_plate:
            messagebox.showerror("Error", "Please detect a license plate first")
            return
            
        report_window = Toplevel(self.root)
        report_window.title("Report Vehicle")
        report_window.geometry("400x500")
        
        # Create form fields
        form_frame = ttk.LabelFrame(report_window, text="Report Details", padding=10)
        form_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        # Incident Type
        ttk.Label(form_frame, text="Incident Type:").pack(pady=2)
        incident_type_var = StringVar(value="Traffic Violation")
        incident_type_menu = ttk.OptionMenu(form_frame, incident_type_var,
                                        "Traffic Violation",
                                        "Hit and Run",
                                        "Suspicious Activity",
                                        "Theft",
                                        "Other")
        incident_type_menu.pack(pady=2, fill=X)
        
        # Description
        ttk.Label(form_frame, text="Description:").pack(pady=2)
        description_text = Text(form_frame, height=4)
        description_text.pack(pady=2, fill=X)
        
        # Location
        ttk.Label(form_frame, text="Location:").pack(pady=2)
        location_entry = ttk.Entry(form_frame)
        location_entry.pack(pady=2, fill=X)
        
        # Incident Date
        ttk.Label(form_frame, text="Incident Date:").pack(pady=2)
        incident_date_entry = ttk.Entry(form_frame)
        incident_date_entry.insert(0, date.today().strftime('%Y-%m-%d'))
        incident_date_entry.pack(pady=2, fill=X)
        
        # Severity Level
        ttk.Label(form_frame, text="Severity Level:").pack(pady=2)
        severity_var = StringVar(value="Medium")
        severity_frame = Frame(form_frame)
        severity_frame.pack(fill=X, pady=2)
        
        ttk.Radiobutton(severity_frame, text="Low", 
                       variable=severity_var, value="Low").pack(side=LEFT, padx=20)
        ttk.Radiobutton(severity_frame, text="Medium", 
                       variable=severity_var, value="Medium").pack(side=LEFT, padx=20)
        ttk.Radiobutton(severity_frame, text="High", 
                       variable=severity_var, value="High").pack(side=LEFT, padx=20)
        
        # Reported By
        ttk.Label(form_frame, text="Reported By:").pack(pady=2)
        reported_by_entry = ttk.Entry(form_frame)
        reported_by_entry.pack(pady=2, fill=X)
        
        def submit_report():
            try:
                # Insert into wanted_list
                self.cursor.execute("""
                    INSERT INTO wanted_list 
                    (vehicle_number, incident_type, description, location, 
                     incident_date, severity_level, reported_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    self.detected_plate,
                    incident_type_var.get(),
                    description_text.get("1.0", END).strip(),
                    location_entry.get().strip(),
                    incident_date_entry.get().strip(),
                    severity_var.get(),
                    reported_by_entry.get().strip()
                ))
                
                self.db.commit()
                self.update_stats_for_plate(self.detected_plate)
                report_window.destroy()
                messagebox.showinfo("Success", "Report submitted successfully!")
                
            except mysql.connector.Error as err:
                messagebox.showerror("Database Error", f"Error submitting report: {err}")
                self.db.rollback()
        
        ttk.Button(form_frame, text="Submit Report",
                  command=submit_report,
                  style='Action.TButton').pack(pady=10)

    def show_registration_form(self):
        if not self.detected_plate:
            messagebox.showerror("Error", "Please detect a license plate first")
            return
            
        # Check if vehicle is already registered
        try:
            self.cursor.execute("SELECT vehicle_number FROM number_registering WHERE vehicle_number = %s", 
                              (self.detected_plate,))
            if self.cursor.fetchone():
                messagebox.showinfo("Info", "Vehicle is already registered")
                return
        except mysql.connector.Error as err:
            messagebox.showerror("Database Error", f"Error checking vehicle registration: {err}")
            return

        # Create registration window
        reg_window = Toplevel(self.root)
        reg_window.title("Vehicle Registration")
        reg_window.geometry("400x500")
        
        # Main frame
        main_frame = ttk.LabelFrame(reg_window, text="Vehicle Registration Details", padding=10)
        main_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        # Vehicle number (display only)
        ttk.Label(main_frame, text="Vehicle Number:", font=('Arial', 11, 'bold')).pack(pady=2)
        ttk.Label(main_frame, text=self.detected_plate, font=('Arial', 11)).pack(pady=2)
        
        # Owner name
        ttk.Label(main_frame, text="Owner Name:").pack(pady=2)
        owner_name_entry = ttk.Entry(main_frame)
        owner_name_entry.pack(pady=2, fill=X)
        
        # Vehicle type
        ttk.Label(main_frame, text="Vehicle Type:").pack(pady=2)
        vehicle_type_var = StringVar(value="Car")
        vehicle_type_menu = ttk.OptionMenu(main_frame, vehicle_type_var, 
                                         "Car", "Bike", "Truck", "Bus", "Other")
        vehicle_type_menu.pack(pady=2)
        
        # Phone number
        ttk.Label(main_frame, text="Phone Number:").pack(pady=2)
        phone_entry = ttk.Entry(main_frame)
        phone_entry.pack(pady=2, fill=X)
        
        # Address
        ttk.Label(main_frame, text="Address:").pack(pady=2)
        address_text = Text(main_frame, height=4)
        address_text.pack(pady=2, fill=X)
        
        def submit_registration():
            # Get values
            owner_name = owner_name_entry.get().strip()
            vehicle_type = vehicle_type_var.get()
            phone_number = phone_entry.get().strip()
            address = address_text.get("1.0", END).strip()
            
            # Validate
            if not all([owner_name, vehicle_type, phone_number, address]):
                messagebox.showerror("Error", "All fields are required")
                return
            
            try:
                # Insert registration
                self.cursor.execute("""
                    INSERT INTO number_registering 
                    (vehicle_number, owner_name, vehicle_type, registration_date, phone_number, address)
                    VALUES (%s, %s, %s, CURDATE(), %s, %s)
                """, (self.detected_plate, owner_name, vehicle_type, phone_number, address))
                
                self.db.commit()
                self.update_detection_results(self.detected_plate)
                reg_window.destroy()
                
            except mysql.connector.Error as err:
                messagebox.showerror("Database Error", f"Error registering vehicle: {err}")
                self.db.rollback()
        
        # Submit button
        ttk.Button(main_frame, text="Register", 
                  command=submit_registration,
                  style='Action.TButton').pack(pady=20)

    def back_video(self):
        if self.cap is None:
            messagebox.showwarning("Warning", "Please select a video first!")
            return
            
        current_time = time.time()
        
        # Reset click count if last click was more than 0.5 second ago
        if current_time - self.last_back_click > 0.5:
            self.back_click_count = 0
        
        self.back_click_count += 1
        self.last_back_click = current_time
        
        if self.back_click_count == 1:
            # First click: Slow down playback
            self.change_speed(-0.5)
        else:
            # Multiple clicks: Skip backwards
            skip_time = 5 * (self.back_click_count - 1)  # 5 seconds for double click, 10 for triple
            
            # Get current frame position
            current_frame = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            # Calculate new position
            new_frame = max(0, current_frame - (skip_time * fps))
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
            
            # Update time display and status
            self.update_time_display(new_frame)
            self.status_value.config(text=f"Skipped back {skip_time} seconds")
            
            # If video is not playing, show the current frame
            if not self.playing:
                ret, frame = self.cap.read()
                if ret:
                    self.current_frame = frame
                    frame = imutils.resize(frame, width=980)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame)
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.video_label.imgtk = imgtk
                    self.video_label.configure(image=imgtk)

    def forward_video(self):
        if self.cap is None:
            messagebox.showwarning("Warning", "Please select a video first!")
            return
            
        current_time = time.time()
        
        # Reset click count if last click was more than 0.5 second ago
        if current_time - self.last_forward_click > 0.5:
            self.forward_click_count = 0
        
        self.forward_click_count += 1
        self.last_forward_click = current_time
        
        if self.forward_click_count == 1:
            # First click: Speed up playback
            self.change_speed(0.5)
        else:
            # Multiple clicks: Skip forward
            skip_time = 5 * (self.forward_click_count - 1)  # 5 seconds for double click, 10 for triple
            
            # Get current frame position and video properties
            current_frame = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            # Calculate new position
            new_frame = min(self.total_frames - 1, current_frame + (skip_time * fps))
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
            
            # Update time display and status
            self.update_time_display(new_frame)
            self.status_value.config(text=f"Skipped forward {skip_time} seconds")
            
            # If video is not playing, show the new frame
            if not self.playing:
                ret, frame = self.cap.read()
                if ret:
                    self.current_frame = frame
                    frame = imutils.resize(frame, width=980)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame)
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.video_label.imgtk = imgtk
                    self.video_label.configure(image=imgtk)

    def show_complaints(self):
        complaints_window = Toplevel(self.root)
        complaints_window.title(f"Complaints for {self.detected_plate}")
        complaints_window.geometry("800x600")
        
        # Create treeview
        columns = ('ID', 'Type', 'Description', 'Location', 'Date', 'Status', 'Fine', 'Reported By')
        tree = ttk.Treeview(complaints_window, columns=columns, show='headings')
        
        # Set column headings
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(complaints_window, orient=VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack widgets
        tree.pack(side=LEFT, fill=BOTH, expand=True, padx=10, pady=5)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        try:
            # Fetch complaints
            self.cursor.execute("""
                SELECT complaint_id, complaint_type, description, location,
                       incident_date, status, fine_amount, reported_by
                FROM complaints 
                WHERE vehicle_number = %s
                ORDER BY created_at DESC
            """, (self.detected_plate,))
            
            # Insert data
            for row in self.cursor.fetchall():
                tree.insert('', END, values=row)
                
        except mysql.connector.Error as err:
            messagebox.showerror("Database Error", f"Error fetching complaints: {err}")

    def update_complaint_count(self):
        try:
            # Count complaints for current vehicle
            self.cursor.execute("""
                SELECT COUNT(*) 
                FROM complaints 
                WHERE vehicle_number = %s
            """, (self.detected_plate,))
            complaint_count = self.cursor.fetchone()[0] or 0

            # Count wanted list reports for current vehicle
            self.cursor.execute("""
                SELECT COUNT(*) 
                FROM wanted_list 
                WHERE vehicle_number = %s
            """, (self.detected_plate,))
            wanted_count = self.cursor.fetchone()[0] or 0

            # Update the label with total count
            total_count = complaint_count + wanted_count
            self.complaint_count_label.config(text=f"Total Reports: {total_count}")
            
            # Update overall statistics
            self.update_stats_for_plate(self.detected_plate)

        except mysql.connector.Error as err:
            print(f"Error updating complaint count: {err}")

    def update_complaint_stats(self):
        try:
            # Count total complaints and their statuses
            self.cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'Pending' OR status = 'In Progress' THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN status = 'Closed' OR status = 'Resolved' THEN 1 ELSE 0 END) as closed
                FROM complaints
            """)
            complaints_stats = self.cursor.fetchone()
            total_complaints = complaints_stats[0] or 0
            active_complaints = complaints_stats[1] or 0
            closed_complaints = complaints_stats[2] or 0

            # Count wanted list reports and their statuses
            self.cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN status IN ('Resolved', 'False Alarm') THEN 1 ELSE 0 END) as closed
                FROM wanted_list
            """)
            wanted_stats = self.cursor.fetchone()
            total_wanted = wanted_stats[0] or 0
            active_wanted = wanted_stats[1] or 0
            closed_wanted = wanted_stats[2] or 0

            # Update statistics labels
            total = total_complaints + total_wanted
            active = active_complaints + active_wanted
            closed = closed_complaints + closed_wanted

            self.total_complaints_label.config(text=f"Total: {total}")
            self.pending_complaints_label.config(text=f"Active: {active}")
            self.closed_complaints_label.config(text=f"Closed: {closed}")
            self.complaints_breakdown_label.config(text=f"Complaints: {total_complaints}")
            self.wanted_breakdown_label.config(text=f"Wanted: {total_wanted}")

        except mysql.connector.Error as err:
            print(f"Error updating complaint statistics: {err}")

    def edit_complaints(self):
        edit_window = Toplevel(self.root)
        edit_window.title(f"Edit Complaints - {self.detected_plate}")
        edit_window.geometry("1000x600")
        
        # Create frames
        top_frame = Frame(edit_window)
        top_frame.pack(fill=X, padx=10, pady=5)
        
        # Stats in top frame
        stats_frame = ttk.LabelFrame(top_frame, text="Statistics")
        stats_frame.pack(fill=X, pady=5)
        
        total_label = Label(stats_frame, text="Total: 0")
        total_label.pack(side=LEFT, padx=10)
        
        pending_label = Label(stats_frame, text="Pending: 0")
        pending_label.pack(side=LEFT, padx=10)
        
        closed_label = Label(stats_frame, text="Closed: 0")
        closed_label.pack(side=LEFT, padx=10)
        
        # Create treeview
        columns = ('ID', 'Type', 'Description', 'Location', 'Date', 'Status', 'Fine')
        tree = ttk.Treeview(edit_window, columns=columns, show='headings')
        
        # Set column headings
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(edit_window, orient=VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack treeview and scrollbar
        tree.pack(fill=BOTH, expand=True, padx=10, pady=5)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        def update_status(complaint_id, new_status):
            try:
                self.cursor.execute("""
                    UPDATE complaints 
                    SET status = %s 
                    WHERE complaint_id = %s
                """, (new_status, complaint_id))
                self.db.commit()
                load_complaints()  # Refresh the list
                self.update_stats_for_plate(self.detected_plate)  # Update main window stats
                self.update_complaint_count()  # Update complaint count
                edit_window.destroy()
            except mysql.connector.Error as err:
                messagebox.showerror("Error", f"Failed to update status: {err}")
                self.db.rollback()
        
        def show_status_menu(event):
            item = tree.selection()[0]
            complaint_id = tree.item(item)['values'][0]
            
            status_menu = Menu(edit_window, tearoff=0)
            for status in ['Pending', 'In Progress', 'Resolved', 'Closed']:
                status_menu.add_command(
                    label=status,
                    command=lambda s=status: update_status(complaint_id, s)
                )
            
            status_menu.post(event.x_root, event.y_root)
        
        tree.bind('<Button-3>', show_status_menu)  # Right-click to show status menu
        
        def load_complaints():
            try:
                # Clear existing items
                for item in tree.get_children():
                    tree.delete(item)
                
                # Load complaints
                self.cursor.execute("""
                    SELECT complaint_id, complaint_type, description, location,
                           incident_date, status, fine_amount
                    FROM complaints 
                    WHERE vehicle_number = %s
                    ORDER BY created_at DESC
                """, (self.detected_plate,))
                
                # Insert data
                for row in self.cursor.fetchall():
                    tree.insert('', END, values=row)
                
                # Update statistics
                self.cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) as pending,
                        SUM(CASE WHEN status = 'Closed' THEN 1 ELSE 0 END) as closed
                    FROM complaints 
                    WHERE vehicle_number = %s
                """, (self.detected_plate,))
                
                stats = self.cursor.fetchone()
                total_label.config(text=f"Total: {stats[0]}")
                pending_label.config(text=f"Pending: {stats[1]}")
                closed_label.config(text=f"Closed: {stats[2]}")
                
            except mysql.connector.Error as err:
                messagebox.showerror("Database Error", f"Error loading complaints: {err}")
        
        # Initial load
        load_complaints()
        
        # Instructions label
        ttk.Label(edit_window, 
                 text="Right-click on a complaint to change its status",
                 font=('Arial', 10, 'italic')).pack(pady=5)

    def edit_plate_number(self):
        if not self.detected_plate:
            return
            
        edit_window = Toplevel(self.root)
        edit_window.title("Edit Plate Number")
        edit_window.geometry("300x150")
        
        # Create and pack widgets
        ttk.Label(edit_window, text="Edit License Plate Number", 
                 font=('Arial', 12, 'bold')).pack(pady=10)
        
        # Entry for new plate number
        plate_var = StringVar(value=self.detected_plate)
        plate_entry = ttk.Entry(edit_window, textvariable=plate_var)
        plate_entry.pack(pady=10, padx=20, fill=X)
        
        def update_plate():
            new_plate = plate_var.get().strip().upper()
            if not new_plate:
                messagebox.showerror("Error", "Plate number cannot be empty!")
                return
                
            # Update the detected plate
            self.detected_plate = new_plate
            self.plate_value.config(text=new_plate)
            
            # Update detection results with new plate number
            self.update_detection_results(new_plate)
            
            # Close edit window
            edit_window.destroy()
        
        # Update button
        ttk.Button(edit_window, text="Update", 
                  command=update_plate).pack(pady=10)

    def copy_plate_number(self):
        plate_number = self.plate_value.cget("text")
        if plate_number != "-":
            self.root.clipboard_clear()
            self.root.clipboard_append(plate_number)
            messagebox.showinfo("Success", "License plate number copied to clipboard!")
        else:
            messagebox.showwarning("Warning", "No license plate number to copy!")

    def save_current_frame(self):
        if self.current_frame is None:
            messagebox.showerror("Error", "No frame available. Please load a video first.")
            return

        # Create directory if it doesn't exist
        save_dir = r"C:\Visual Studio codes\Mini Projects\License-Plate-Detection-OpenCV-and-Py-Tesseract-master\Get_car_plate"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        # Get the current plate number
        plate_number = self.plate_value.cget("text")
        
        # Check if plate number is valid (not empty, not "-", and not the default message)
        if plate_number in ["-", "Video loaded. Click Play to start.", "", None]:
            # First try to detect the plate
            self.detect_current_frame()
            plate_number = self.plate_value.cget("text")
            
            # If still no valid plate, ask for manual input
            if plate_number in ["-", "Video loaded. Click Play to start.", "", None]:
                plate_number = simpledialog.askstring("Input", "Enter the plate number for this image:")
                if not plate_number:  # User cancelled
                    return
                # Update the plate value display
                self.plate_value.config(text=plate_number)
        
        # Clean the filename by removing invalid characters
        plate_number = re.sub(r'[<>:"/\\|?*]', '_', plate_number)
        
        # Save the image
        image_path = os.path.join(save_dir, f"{plate_number}.jpg")
        counter = 1
        while os.path.exists(image_path):
            image_path = os.path.join(save_dir, f"{plate_number}_{counter}.jpg")
            counter += 1
            
        cv2.imwrite(image_path, self.current_frame)
        messagebox.showinfo("Success", f"Image saved as {os.path.basename(image_path)}")

    def change_db_config(self):
        """Change database configuration"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'app_config.json')
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Create a new window for database configuration
            db_window = Toplevel(self.root)
            db_window.title("Database Configuration")
            db_window.geometry("400x350")
            
            # Create form fields
            form_frame = ttk.LabelFrame(db_window, text="Database Settings", padding=10)
            form_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
            
            # Host
            ttk.Label(form_frame, text="Host:").pack(pady=2)
            host_entry = ttk.Entry(form_frame, width=40)
            host_entry.insert(0, config['database']['host'])
            host_entry.pack(pady=2)
            
            # User
            ttk.Label(form_frame, text="User:").pack(pady=2)
            user_entry = ttk.Entry(form_frame, width=40)
            user_entry.insert(0, config['database']['user'])
            user_entry.pack(pady=2)
            
            # Password
            ttk.Label(form_frame, text="Password:").pack(pady=2)
            password_entry = ttk.Entry(form_frame, width=40, show='*')
            password_entry.insert(0, config['database']['password'])
            password_entry.pack(pady=2)
            
            # Database
            ttk.Label(form_frame, text="Database:").pack(pady=2)
            database_entry = ttk.Entry(form_frame, width=40)
            database_entry.insert(0, config['database']['database'])
            database_entry.pack(pady=2)
            
            # Status label for connection test
            status_label = ttk.Label(form_frame, text="", font=('Arial', 10))
            status_label.pack(pady=5)
            
            def test_connection():
                try:
                    # Create a test connection with current form values
                    test_db = mysql.connector.connect(
                        host=host_entry.get().strip(),
                        user=user_entry.get().strip(),
                        password=password_entry.get().strip(),
                        database=database_entry.get().strip()
                    )
                    
                    # If connection successful, close it
                    if test_db:
                        test_db.close()
                        status_label.config(
                            text="✓ Connection successful!",
                            foreground='green'
                        )
                except mysql.connector.Error as err:
                    status_label.config(
                        text=f"✗ Connection failed: {str(err)}",
                        foreground='red'
                    )
            
            def save_db_config():
                try:
                    # Update configuration
                    config['database']['host'] = host_entry.get().strip()
                    config['database']['user'] = user_entry.get().strip()
                    config['database']['password'] = password_entry.get().strip()
                    config['database']['database'] = database_entry.get().strip()
                    
                    # Save to file
                    with open(config_path, 'w') as f:
                        json.dump(config, f, indent=4)
                    
                    # Try to reconnect with new settings
                    if self.db:
                        self.db.close()
                    self.db = None
                    self.init_database()
                    
                    messagebox.showinfo("Success", "Database configuration updated successfully!")
                    db_window.destroy()
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update configuration: {str(e)}")
            
            # Buttons frame
            buttons_frame = Frame(form_frame)
            buttons_frame.pack(fill=X, pady=10)
            
            # Test Connection button
            ttk.Button(buttons_frame, text="Test Connection",
                      command=test_connection,
                      style='Regular.TButton').pack(side=LEFT, padx=5)
            
            # Save button
            ttk.Button(buttons_frame, text="Save Configuration",
                      command=save_db_config,
                      style='Action.TButton').pack(side=LEFT, padx=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load configuration: {str(e)}")

    def change_photos_path(self):
        """Change photos save path configuration"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'app_config.json')
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Ask for directory
            new_path = filedialog.askdirectory(
                title="Select Photos Save Directory",
                initialdir=config.get('save_path', os.path.dirname(__file__))
            )
            
            if new_path:
                # Convert to proper path format
                new_path = new_path.replace('\\', '/')
                
                # Update configuration
                config['save_path'] = new_path
                
                # Save to file
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=4)
                
                messagebox.showinfo("Success", "Photos save path updated successfully!")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update save path: {str(e)}")

if __name__ == "__main__":
    root = Tk()
    app = LicensePlateDetector(root)
    root.mainloop()