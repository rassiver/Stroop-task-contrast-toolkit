from psychopy import visual, core, event, data, gui
import random
import pandas as pd
import numpy as np
import threading
from pylsl import StreamInfo, StreamOutlet
import pylsl  # Add this line to access pylsl.local_clock
# Get LSL version info (works on all versions)
print(f"LSL protocol version: {pylsl.library_version()}")

# Alternative IPv6 check for older pylsl
try:
    # Try modern method first
    from pylsl import get_config
    print(f"IPv6 support: {get_config('ipv6')}")
except ImportError:
    # Fallback for older versions
    print("IPv6 status: Unknown (pylsl too old for config check)")
    print("Forcing IPv4 compatibility...")
    import os
    os.environ['LSL_IPV4'] = 'allow'  # Force IPv4 mode
import os
# Force IPv4 for LSL (works on all pylsl versions)
os.environ['LSL_IPV4'] = 'allow'  # Bypass IPv6 completely
os.environ['LSL_LOCALHOST'] = '127.0.0.1'  # Explicit local binding

# Set up experiment info
exp_info = {
    'participant': '',
    'session': '001',
}

import time
unique_id = f"stroop_{int(time.time())}"  # Unique ID based on timestamp

# Enhance the ResilientOutlet class
class ResilientOutlet:
    def __init__(self):
        self.outlet = None
        self.last_successful_send = 0  # Critical initialization
        self.lock = threading.Lock()   # Thread safety
        self.info = StreamInfo(
            name='StroopMarkers',
            type='Markers',
            channel_count=1,
            nominal_srate=0,
            channel_format='string',
            source_id=f'stroop_{exp_info["participant"]}'
        )
        channels = self.info.desc().append_child("channels")
        channels.append_child("channel").append_child_value("label", "Markers")
        self.info.desc().append_child_value("manufacturer", "PsychoPy")
        self.info.desc().append_child_value("created_at", time.strftime("%Y-%m-%d %H:%M:%S"))
        self.create_outlet()
        
    def create_outlet(self, max_attempts=3):
        for attempt in range(max_attempts):
            try:
                self.outlet = StreamOutlet(self.info)
                print(f"✓ LSL outlet created (attempt {attempt+1})")
                print(f"Stream Name: {self.info.name()}")
                return True
            except Exception as e:
                print(f"⚠️ Attempt {attempt+1} failed: {str(e)}")
                if attempt < max_attempts-1:
                    import time; time.sleep(1)
        return False
    
    def push_sample(self, marker, timestamp=None):
        """Wrapper with auto-recovery"""
        with self.lock:  # Thread-safe
            if timestamp is None:
                timestamp = pylsl.local_clock()
            
            if isinstance(marker, (list, tuple)):
                marker = marker[0] if len(marker) > 0 else ""
            marker_str = str(marker)
            
            try:
                if self.outlet:
                    self.outlet.push_sample([marker_str], timestamp)
                    self.last_successful_send = time.time()
                    return True
            except Exception as e:
                current_time = time.time()
                time_since_last = current_time - self.last_successful_send
                print(f"⚠️ Marker '{marker_str}' failed: {str(e)}. Time since last success: {time_since_last:.2f}s")
                
                if time_since_last > 3.0:  
                    print("Attempting outlet recovery...")
                    if self.create_outlet():
                        try:
                            if self.outlet:
                                self.outlet.push_sample([marker_str], timestamp)
                                self.last_successful_send = time.time()
                                return True
                        except Exception as e2:
                            print(f"⚠️ Recovery failed for '{marker_str}': {str(e2)}")
            return False

# Replace your outlet creation with:
outlet = ResilientOutlet()

if outlet.outlet:
    print("Stream created successfully")
    # Get stream info from the original StreamInfo object instead
    print(f"Name: {outlet.info.name()}")
    print(f"Type: {outlet.info.type()}")
    print(f"Source ID: {outlet.info.source_id()}")
else:
    print("Warning: No LSL outlet created")

def send_event_code(outlet, code, description="", max_retries=3):
    """Send an event code as a pure integer marker (string format)"""
    timestamp = pylsl.local_clock()

    success = False
    for attempt in range(max_retries):
        try:
            # Send the code as a simple integer string (not "CODE_XXX", just "101" etc)
            outlet.push_sample([str(code)], timestamp)
            print(f"✓ Sent code {code}: {description}")  # Still print description for your logging
            success = True
            break
        except Exception as e:
            print(f"⚠️ Send failed (attempt {attempt+1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                core.wait(0.5)

    if not success:
        print(f"❌ Failed to send code {code}: {description} after {max_retries} attempts")

    return success

# ===== ADD STEP 4 HERE =====
def send_keepalive(outlet):
    """Send periodic keepalive markers every 5 seconds"""
    while True:
        outlet.push_sample("KEEPALIVE")
        time.sleep(5.0)

# Start keepalive thread
keepalive_thread = threading.Thread(
    target=send_keepalive, 
    args=(outlet,), 
    daemon=True
)
keepalive_thread.start()
# ===== END STEP 4 ADDITION =====

# Send initialization pulses
try:
    # First confirm the outlet exists
    if not outlet.outlet:
        print("⚠️ No LSL outlet available. Creating new one...")
        outlet.create_outlet()
        if not outlet.outlet:
            print("❌ Failed to create LSL outlet. Continuing without LSL markers.")
    
    # Send initialization codes with logging
    print("Sending system initialization codes...")
    init_success = send_event_code(outlet, 900, 'SYSTEM_INIT')
    core.wait(0.5)  # Add delay between critical markers
    
    nirx_success = send_event_code(outlet, 901, 'NIRX_CONNECT')
    core.wait(0.5)  # Add delay between critical markers
    
    aurora_success = send_event_code(outlet, 902, 'AURORA_READY')
    
    # ✅ Only proceed if all codes were sent successfully
    if init_success and nirx_success and aurora_success:
        print("✓ System initialization sequence complete")
        core.wait(2.0)  # Buffer time for devices to initialize
    else:
        print("⚠️ System initialization incomplete. Some markers may not be recorded.")
        # Continue anyway, as the experiment should run even with marker issues
        
except Exception as e:
    print(f"⚠️ System initialization failed: {str(e)}")
   
# Display dialog box for participant info
dlg = gui.DlgFromDict(dictionary=exp_info, title='Stroop Task - HIGH CONTRAST')
if not dlg.OK:
    core.quit()  # Cancel was pressed

# Set up the experiment window - high contrast uses black background
win = visual.Window([800, 600], color="black", units="pix", fullscr=True)

# Test LSL connection before starting experiment
print("Testing LSL connection...")
test_success = True
for i in range(5):
    if not send_event_code(outlet, 800+i, f'TEST_LSL_{i}'):
        test_success = False
        break
    core.wait(0.1)

if test_success:
    print("✓ LSL connection test passed")
else:
    print("⚠️ LSL connection test failed. Experiment will continue but marker recording may be unreliable.")
    
    # Ask user if they want to continue
    continue_text = visual.TextStim(win, 
        text="Warning: LSL marker connection may be unreliable.\n\nPress 'C' to continue anyway or 'Q' to quit.", 
        color="red", height=30)
    continue_text.draw()
    win.flip()
    keys = event.waitKeys(keyList=["c", "q"])
    if "q" in keys:
        win.close()
        core.quit()

# Define text for Stroop stimuli
stroop_text = {
    "red": "RED",
    "green": "GREEN",
    "blue": "BLUE",
    "yellow": "YELLOW"
}

# Define bright colors for high contrast (RGB values)
color_values = {
    "red": [1.0, 0.0, 0.0],    # Bright red
    "green": [0.0, 1.0, 0.0],  # Bright green
    "blue": [0.0, 0.0, 1.0],   # Bright blue
    "yellow": [1.0, 1.0, 0.0],  # Bright yellow
    "white": [1, 1, 1]           # White (for fixation)
}

# Define visual stimuli
window_size = win.size
background = visual.Rect(
    win, 
    width=window_size[0]*2,
    height=window_size[1]*2, 
    fillColor="black",
    pos=(0, 0)
)
fixation = visual.TextStim(win, text="+", color="white", height=40)

# Define visual stimuli
fixation = visual.TextStim(win, text="+", color="white", height=40)
correct_feedback = visual.TextStim(win, text="✓", color="white", height=40)
incorrect_feedback = visual.TextStim(win, text="✗", color="white", height=40)
neutral_stim = visual.TextStim(win, text="◯", color="white", height=40)

# Define Stroop stimuli conditions
conditions = pd.DataFrame([
    ["yellowyellow", "y", 1, "yellow yellow"], 
    ["yellowgreen", "g", 0, "yellow green"], 
    ["yellowblue", "b", 0, "yellow blue"], 
    ["yellowred", "r", 0, "yellow red"],
    ["redyellow", "y", 0, "red yellow"], 
    ["redgreen", "g", 0, "red green"], 
    ["redblue", "b", 0, "red blue"], 
    ["redred", "r", 1, "red red"],
    ["greenyellow", "y", 0, "green yellow"], 
    ["greengreen", "g", 1, "green green"], 
    ["greenblue", "b", 0, "green blue"], 
    ["greenred", "r", 0, "green red"],
    ["blueyellow", "y", 0, "blue yellow"], 
    ["bluegreen", "g", 0, "blue green"], 
    ["blueblue", "b", 1, "blue blue"], 
    ["bluered", "r", 0, "blue red"]
], columns=["stimulus", "correct_response", "congruent", "condition_name"])

# Separate congruent and incongruent conditions
congruent_conditions = conditions[conditions["congruent"] == 1]
incongruent_conditions = conditions[conditions["congruent"] == 0]

# Set up files to save results
raw_data_file = f"stroop_high_contrast_raw_{exp_info['participant']}_{exp_info['session']}.csv"
summary_data_file = f"stroop_high_contrast_summary_{exp_info['participant']}_{exp_info['session']}.csv"
results = []

def check_for_escape():
    keys = event.getKeys(keyList=['escape'])
    if 'escape' in keys:
        if results:
            save_data(results, "partial")
        win.close()
        core.quit()

def save_data(results_data, prefix=""):
    raw_df = pd.DataFrame(results_data)
    if not raw_df.empty:
        raw_df.to_csv(f"{prefix}_{raw_data_file}", index=False)
    
    if len(results_data) > 0:
        df_stroop = pd.DataFrame([r for r in results_data if r["block_type"] in ["congruent", "incongruent"]])
        
        if not df_stroop.empty:
            congruent_trials = df_stroop[df_stroop["block_type"] == "congruent"]
            incongruent_trials = df_stroop[df_stroop["block_type"] == "incongruent"]
            
            con_correct = sum(1 for r in congruent_trials.itertuples() if r.correct == True)
            incon_correct = sum(1 for r in incongruent_trials.itertuples() if r.correct == True)
            
            con_correct_trials = congruent_trials[congruent_trials["correct"] == True]
            incon_correct_trials = incongruent_trials[incongruent_trials["correct"] == True]
            
            con_rt = con_correct_trials["rt"].mean() if not con_correct_trials.empty else float('nan')
            incon_rt = incon_correct_trials["rt"].mean() if not incon_correct_trials.empty else float('nan')
            
            stroop_effect = incon_rt - con_rt if not (pd.isna(incon_rt) or pd.isna(con_rt)) else float('nan')
            
            summary_data = {
                "measure": [
                    "participant_id",
                    "session",
                    "contrast_condition",
                    "congruent_trials_total",
                    "incongruent_trials_total",
                    "congruent_correct",
                    "incongruent_correct",
                    "congruent_accuracy",
                    "incongruent_accuracy",
                    "congruent_mean_rt",
                    "incongruent_mean_rt",
                    "stroop_effect"
                ],
                "value": [
                    exp_info['participant'],
                    exp_info['session'],
                    "high",  # Changed from "low" to "high"
                    len(congruent_trials),
                    len(incongruent_trials),
                    con_correct,
                    incon_correct,
                    con_correct / len(congruent_trials) if len(congruent_trials) > 0 else 0,
                    incon_correct / len(incongruent_trials) if len(incongruent_trials) > 0 else 0,
                    con_rt,
                    incon_rt,
                    stroop_effect
                ]
            }
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_csv(f"{prefix}_{summary_data_file}", index=False)
            
            return con_rt, incon_rt, stroop_effect
    
    return None, None, None

# Experiment instructions
instructions1 = visual.TextStim(win, text="Welcome to the Stroop Task!\n\nIn this task, you will see color words presented in different colors.\n\nYour task is to respond to the COLOR of the text, not the word itself.\n\nPress space to continue. (Press escape at any time to exit)", color="white", wrapWidth=700)
instructions1.draw()
win.flip()
event.waitKeys(keyList=["space", "escape"])
if event.getKeys(keyList=["escape"]):
    win.close()
    core.quit()

instructions2 = visual.TextStim(win, text="Press:\nR = Red\nG = Green\nB = Blue\nY = Yellow\n\nYou will complete the HIGH CONTRAST version of this task.\n\nThere will be neutral screens between blocks.\n\nPress space to start. (Press escape at any time to exit)", color="white", wrapWidth=700)
instructions2.draw()
win.flip()
event.waitKeys(keyList=["space", "escape"])
if event.getKeys(keyList=["escape"]):
    win.close()
    core.quit()
    
send_event_code(outlet, 0, 'experiment_start')

def create_stroop_stimulus(stimulus_code):
    for color_name in ["red", "green", "blue", "yellow"]:
        if stimulus_code.startswith(color_name):
            word = color_name
            color = stimulus_code[len(word):]
            if color == "": color = word  # For congruent trials
            break
    
    return visual.TextStim(
        win, 
        text=stroop_text[word], 
        color=color_values[color], 
        height=80, 
        bold=True, 
        pos=[0, 0]
    )

def run_congruent_block(block_num, num_trials=8):
    block_results = []
    block_trials = congruent_conditions.sample(n=num_trials, replace=True).to_dict(orient="records")
    
    for trial in block_trials:
        # Fixation cross
        fixation.draw()
        win.flip()
        core.wait(0.5)
        check_for_escape()
        
        # Clear screen
        win.flip()
        core.wait(0.1)
        check_for_escape()
        
        # Show Stroop stimulus
        send_event_code(outlet, 1, f'trial_start_{trial["stimulus"]}')  # Code 1 for trial start
        stim = create_stroop_stimulus(trial["stimulus"])
        stim.draw()
        win.flip()
        
        # Wait for response
        clock = core.Clock()
        keys = event.waitKeys(maxWait=2, keyList=["r", "g", "b", "y", "escape"], timeStamped=clock)
        
        if keys and keys[0][0] == "escape":
            if block_results:
                results.extend(block_results)
                save_data(results, "partial")
            win.close()
            core.quit()
        
        # Clear screen
        win.flip()
        core.wait(0.1)
        check_for_escape()
        
        # Process response
        if keys:
            key, rt = keys[0]
            correct = (key == trial["correct_response"])
            response_code = 2 if correct else 3  # 2=correct, 3=incorrect
            send_event_code(outlet, response_code, f'response_{key}_{"correct" if correct else "incorrect"}')
        else:
            key, rt = "None", 2.0
            correct = False
            send_event_code(outlet, 4, 'no_response')  # Code 4 for no response
        
        # Removes feedback display but keep ITI
        background.draw()
        win.flip()
        iti_duration = random.uniform(0.8, 1.2)  # Adjust these values as needed
        core.wait(iti_duration)
        check_for_escape()
        
        # Save results
        block_results.append({
            "participant": exp_info['participant'],
            "session": exp_info['session'],
            "block": block_num,
            "contrast": "high",
            "block_type": "congruent", 
            "stimulus": trial["stimulus"], 
            "response": key, 
            "correct": correct, 
            "rt": rt
        })
    
    return block_results

def run_incongruent_block(block_num, num_trials=8):
    block_results = []
    block_trials = incongruent_conditions.sample(n=num_trials, replace=True).to_dict(orient="records")
    
    for trial in block_trials:
        # Fixation cross
        fixation.draw()
        win.flip()
        core.wait(0.5)
        check_for_escape()
        
        # Clear screen
        win.flip()
        core.wait(0.1)
        check_for_escape()
        
        # Show Stroop stimulus
        send_event_code(outlet, 1, f'trial_start_{trial["stimulus"]}')  # Code 1 for trial start
        stim = create_stroop_stimulus(trial["stimulus"])
        stim.draw()
        win.flip()
        
        # Wait for response
        clock = core.Clock()
        keys = event.waitKeys(maxWait=2, keyList=["r", "g", "b", "y", "escape"], timeStamped=clock)
        
        if keys and keys[0][0] == "escape":
            if block_results:
                results.extend(block_results)
                save_data(results, "partial")
            win.close()
            core.quit()
        
        # Clear screen
        win.flip()
        core.wait(0.1)
        check_for_escape()
        
        # Process response
        if keys:
            key, rt = keys[0]
            correct = (key == trial["correct_response"])
            response_code = 2 if correct else 3  # 2=correct, 3=incorrect
            send_event_code(outlet, response_code, f'response_{key}_{"correct" if correct else "incorrect"}')
        else:
            key, rt = "None", 2.0
            correct = False
            send_event_code(outlet, 4, 'no_response')  # Code 4 for no response
        
        
        # Removes feedback display but keep ITI
        background.draw()
        win.flip()
        iti_duration = random.uniform(0.8, 1.2)  # Adjust these values as needed
        core.wait(iti_duration)
        check_for_escape()
        
        # Save results
        block_results.append({
            "participant": exp_info['participant'],
            "session": exp_info['session'],
            "block": block_num,
            "contrast": "high",
            "block_type": "incongruent", 
            "stimulus": trial["stimulus"], 
            "response": key, 
            "correct": correct, 
            "rt": rt
        })
    
    return block_results

def run_neutral_block():
    duration = random.uniform(18, 22)
    neutral_stim.draw()
    win.flip()
    
    start_time = core.getTime()
    while core.getTime() - start_time < duration:
        check_for_escape()
        core.wait(0.1)
    
    return duration

# Block sequence
block_sequence = [
    ("congruent", 1),
    ("neutral", None),
    ("incongruent", 2),
    ("neutral", None),
    ("congruent", 3),
    ("neutral", None),
    ("incongruent", 4),
    ("neutral", None),
    ("congruent", 5),
    ("neutral", None),
    ("incongruent", 6)
]

# Start message
block_msg = visual.TextStim(win, text="Ready to begin the experiment.\n\nPress space to start.", color="white")
block_msg.draw()
win.flip()
event.waitKeys(keyList=["space", "escape"])
if event.getKeys(keyList=["escape"]):
    win.close()
    core.quit()

# Run blocks
for block_type, block_num in block_sequence:
    if block_type == "congruent":
        # Block start - uses code 101 for block 1, 102 for block 2, etc.
        send_event_code(outlet, 100+block_num, f'block_{block_num}_congruent_start')
        block_results = run_congruent_block(block_num)
        results.extend(block_results)
        # Block end - uses code 151 for block 1, 152 for block 2, etc.
        send_event_code(outlet, 150+block_num, f'block_{block_num}_congruent_end')
        
    elif block_type == "incongruent":
        # Block start - uses code 201 for block 1, 202 for block 2, etc.
        send_event_code(outlet, 200+block_num, f'block_{block_num}_incongruent_start')
        block_results = run_incongruent_block(block_num)
        results.extend(block_results)
        # Block end - uses code 251 for block 1, 252 for block 2, etc.
        send_event_code(outlet, 250+block_num, f'block_{block_num}_incongruent_end')
        
    elif block_type == "neutral":
        # Neutral blocks use fixed codes 300-399
        send_event_code(outlet, 300, 'neutral_block_start')
        duration = run_neutral_block()
        send_event_code(outlet, 350, 'neutral_block_end')                    # MARKER: Neutral block ends
        results.append({
            "participant": exp_info['participant'],
            "session": exp_info['session'],
            "block": "neutral",
            "contrast": "low",
            "block_type": "neutral", 
            "stimulus": "neutral", 
            "response": "n/a", 
            "correct": "n/a", 
            "rt": duration
        })

congruent_rt, incongruent_rt, stroop_effect = save_data(results)

if congruent_rt is not None and incongruent_rt is not None and not (pd.isna(congruent_rt) or pd.isna(incongruent_rt)):
    feedback_text = f"Your speed in correct trials:\n\nCongruent blocks: {congruent_rt:.3f} sec\nIncongruent blocks: {incongruent_rt:.3f} sec\n\nYour Stroop effect: {stroop_effect:.3f} sec\n\nPress space to exit."
else:
    feedback_text = "Thank you for participating!\n\nPress space to exit."

feedback = visual.TextStim(win, text=feedback_text, color="white", wrapWidth=700)
feedback.draw()
win.flip()
event.waitKeys(keyList=["space", "escape"])

# Replace the existing cleanup code with this more robust version
print("Shutting down LSL connection...")
try:
    # Send final marker
    send_event_code(outlet, 999, 'EXPERIMENT_COMPLETE')
    core.wait(1.0)  # Wait to ensure marker is sent
    
    # Clean shutdown
    if keepalive_thread.is_alive():
        print("Waiting for keepalive thread to finish...")
        keepalive_thread.join(timeout=2.0)
        
    # Force outlet closure
    if hasattr(outlet, 'outlet') and outlet.outlet:
        del outlet.outlet
    del outlet
    print("✓ LSL connection closed")
    
except Exception as e:
    print(f"⚠️ Error during LSL shutdown: {str(e)}")

# Close window
win.close()
core.quit()