import tkinter as tk
import json

from src.steamGifts import SteamGifts
from src.log_colors import *


class Display(tk.Tk):
    config = dict()
    log_counter = 0
    sg_bot = None

    def __init__(self):
        super().__init__()

        # First load the config files.
        self.load_config()

        # Set the title of the application
        self.title('SteamGifts Giveaway Enter Tool')

        # Create the PATH fill-in field.
        tk.Label(self, text="Google Chrome Profile Path:").grid(row=0, sticky=tk.NSEW)
        self.entry_chrome_profile_path = tk.Entry(self, text=self.config["chrome-profile-path"])
        self.entry_chrome_profile_path.grid(row=1, sticky=tk.NSEW)
        self.entry_chrome_profile_path.insert(0, self.config["chrome-profile-path"])

        # Create the enter button
        tk.Button(self, text='Enter Giveaways', command=self.enter).grid(row=2, sticky=tk.NSEW, pady=4)

        # Make the grid expand.
        tk.Grid.rowconfigure(self, 3, weight=1)
        tk.Grid.columnconfigure(self, 1, weight=1)

        # Create the quit button
        tk.Button(self, text='Quit', command=self.quit).grid(row=4, sticky=tk.NSEW, pady=4)

        # Create the scroll text field.
        text_container = tk.Frame(self, borderwidth=1, relief="sunken", background="white")
        self.log = tk.Listbox(text_container, width=24, height=13, borderwidth=0, highlightthickness=0)
        text_vsb = tk.Scrollbar(text_container, orient="vertical", command=self.log.yview)
        text_hsb = tk.Scrollbar(text_container, orient="horizontal", command=self.log.xview)
        self.log.configure(yscrollcommand=text_vsb.set, xscrollcommand=text_hsb.set)
        self.log.bindtags((self.log, self, "all"))

        self.log.grid(row=0, column=0, sticky="nsew", pady=10, padx=10)
        text_vsb.grid(row=0, column=1, sticky="ns")
        text_hsb.grid(row=1, column=0, sticky="ew")

        text_container.grid_rowconfigure(0, weight=1)
        text_container.grid_columnconfigure(0, weight=1)

        text_container.grid(column=1, row=0, rowspan=5, pady=10, padx=10, sticky=tk.NSEW)

        tk.mainloop()

    def load_config(self):
        with open('../config.json') as f:
            self.config = json.load(f)

    def store_config(self):
        with open('data.txt', 'w') as f:
            json.dump(self.config, f)

    def log_console_text(self, text, config=None):
        # Split the lines.
        split_lines = str(text).split("\n")

        # Add each line separately to the log.
        for split_line in split_lines:
            # Normal console log.
            print(split_line)

            # Insert the line.
            self.log.insert(tk.END, split_line)

            # Set the coloring.
            if config is not None:
                self.log.itemconfig(self.log_counter, config)

            # Increment the counter.
            self.log_counter = self.log_counter + 1
            self.update()

    def enter(self):
        self.log_console_text("Starting the SteamGifts enter bot.", config=log_verbose)

        # Start the bot TODO: Add multi-threading to allow functioning GUI.
        self.sg_bot = SteamGifts(self.config, self)

    def show_entry_fields(self):
        print("First Name: %s" % (self.entry_chrome_profile_path.get()))


Display()
