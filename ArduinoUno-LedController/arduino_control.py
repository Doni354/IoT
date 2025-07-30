import serial
import tkinter as tk

arduino = serial.Serial('COM5', 9600)

def toggle_red():
    if red_var.get():
        arduino.write(b'R')  # Red ON
    else:
        arduino.write(b'r')  # Red OFF

def toggle_green():
    if green_var.get():
        arduino.write(b'G')  # Green ON
    else:
        arduino.write(b'g')  # Green OFF

def blink_mode():
    arduino.write(b'B')  # Blink mode

def speed_up():
    arduino.write(b'S')  # Speed to 100ms

def default_speed():
    arduino.write(b'D')  # Back to 500ms

root = tk.Tk()
root.title("Arduino LED Switches")

# Switch Variables
red_var = tk.BooleanVar()
green_var = tk.BooleanVar()

# Switch Buttons
tk.Checkbutton(root, text="Red ON", variable=red_var, command=toggle_red).pack(pady=5)
tk.Checkbutton(root, text="Green ON", variable=green_var, command=toggle_green).pack(pady=5)

# Blink Mode
tk.Button(root, text="Blink", command=blink_mode, width=20).pack(pady=10)

# Speed Control
tk.Button(root, text="Speed Up Blink (100ms)", command=speed_up, width=25).pack(pady=5)
tk.Button(root, text="Reset Blink Speed (500ms)", command=default_speed, width=25).pack(pady=5)

root.mainloop()
