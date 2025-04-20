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
    """Send an event code with description and guarantee delivery"""
    timestamp = pylsl.local_clock()
    code_str = f"CODE_{code:03d}"
    
    success = False
    for attempt in range(max_retries):
        try:
            # Send both markers with proper encoding
            outlet.push_sample(code_str, timestamp)
            outlet.push_sample(description, timestamp + 0.001)
            print(f"✓ Sent {code_str}: {description}")
            success = True
            break
        except Exception as e:
            print(f"⚠️ Send failed (attempt {attempt+1}/{max_retries}): {str(e)}")
            if attempt < max_retries-1:
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

background = visual.Rect(win, width=800, height=600, fillColor="black", lineColor=None)

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

# Define colors (RGB values)
color_schemes = {
    'low': {
        "red": [0.7, 0.0, 0.0],     # Desaturated red
        "green": [0.0, 0.7, 0.0],   # Desaturated green
        "blue": [0.0, 0.0, 0.7],    # Desaturated blue
        "yellow": [0.7, 0.7, 0.0],  # Desaturated yellow
        "neutral_bg": [0, 0, 0],  # Constant background
        "white": [1, 1, 1]          # For fixation/feedback
    },
    'high': {
        "red": [1.0, 0, 0],       # Fully saturated colors
        "green": [0, 1.0, 0],
        "blue": [0, 0, 1.0],
        "yellow": [1.0, 1.0, 0],
        "neutral_bg": [0, 0, 0],
        "white": [1, 1, 1]
    }
}

# Define visual stimuli
fixation = visual.TextStim(win, text="+", color="white", height=40)
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

# Block definitions
block_definitions = [
    # Low contrast blocks (some with 15 trials)
    {'type': 'congruent', 'contrast': 'low', 'trials': 8},
    {'type': 'congruent', 'contrast': 'low', 'trials': 15},  # Extended block
    {'type': 'incongruent', 'contrast': 'low', 'trials': 8},
    {'type': 'incongruent', 'contrast': 'low', 'trials': 15}, # Extended block
    
    # High contrast blocks (some with 15 trials)
    {'type': 'congruent', 'contrast': 'high', 'trials': 8},
    {'type': 'congruent', 'contrast': 'high', 'trials': 15},  # Extended block
    {'type': 'incongruent', 'contrast': 'high', 'trials': 8},
    {'type': 'incongruent', 'contrast': 'high', 'trials': 15}, # Extended block
    
    # Neutral blocks (unchanged)
    {'type': 'neutral', 'contrast': None}
] * 2  # Double to reach 16 blocks (8x2)

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
        # Separate into different conditions
        df_stroop = pd.DataFrame([r for r in results_data if r["block_type"] in ["congruent", "incongruent"]])
        
        results = {
            'low': {'congruent': [], 'incongruent': []},
            'high': {'congruent': [], 'incongruent': []},
            'overall': {'congruent': [], 'incongruent': []}
        }
        
        if not df_stroop.empty:
            # Process low contrast data
            low_contrast = df_stroop[df_stroop["contrast"] == "low"]
            low_congruent = low_contrast[low_contrast["block_type"] == "congruent"]
            low_incongruent = low_contrast[low_contrast["block_type"] == "incongruent"]
            
            # Process high contrast data
            high_contrast = df_stroop[df_stroop["contrast"] == "high"]
            high_congruent = high_contrast[high_contrast["block_type"] == "congruent"]
            high_incongruent = high_contrast[high_contrast["block_type"] == "incongruent"]
            
            # Calculate metrics for each condition
            def calculate_metrics(condition_df, condition_name):
                correct_trials = condition_df[condition_df["correct"] == True]
                return {
                    'count': len(condition_df),
                    'correct': len(correct_trials),
                    'accuracy': len(correct_trials)/len(condition_df) if len(condition_df) > 0 else 0,
                    'mean_rt': correct_trials["rt"].mean() if not correct_trials.empty else float('nan')
                }
            
            metrics = {
                'low_congruent': calculate_metrics(low_congruent, "low_congruent"),
                'low_incongruent': calculate_metrics(low_incongruent, "low_incongruent"),
                'high_congruent': calculate_metrics(high_congruent, "high_congruent"),
                'high_incongruent': calculate_metrics(high_incongruent, "high_incongruent")
            }
            
            # Calculate Stroop effects
            stroop_effects = {
                'low': metrics['low_incongruent']['mean_rt'] - metrics['low_congruent']['mean_rt'],
                'high': metrics['high_incongruent']['mean_rt'] - metrics['high_congruent']['mean_rt']
            }
            
            # Create summary data
            summary_data = {
                "measure": [
                    "participant_id", "session",
                    "low_contrast_congruent_trials", "low_contrast_congruent_correct", "low_contrast_congruent_accuracy", "low_contrast_congruent_mean_rt",
                    "low_contrast_incongruent_trials", "low_contrast_incongruent_correct", "low_contrast_incongruent_accuracy", "low_contrast_incongruent_mean_rt",
                    "low_contrast_stroop_effect",
                    "high_contrast_congruent_trials", "high_contrast_congruent_correct", "high_contrast_congruent_accuracy", "high_contrast_congruent_mean_rt",
                    "high_contrast_incongruent_trials", "high_contrast_incongruent_correct", "high_contrast_incongruent_accuracy", "high_contrast_incongruent_mean_rt",
                    "high_contrast_stroop_effect"
                ],
                "value": [
                    exp_info['participant'], exp_info['session'],
                    metrics['low_congruent']['count'], metrics['low_congruent']['correct'], metrics['low_congruent']['accuracy'], metrics['low_congruent']['mean_rt'],
                    metrics['low_incongruent']['count'], metrics['low_incongruent']['correct'], metrics['low_incongruent']['accuracy'], metrics['low_incongruent']['mean_rt'],
                    stroop_effects['low'],
                    metrics['high_congruent']['count'], metrics['high_congruent']['correct'], metrics['high_congruent']['accuracy'], metrics['high_congruent']['mean_rt'],
                    metrics['high_incongruent']['count'], metrics['high_incongruent']['correct'], metrics['high_incongruent']['accuracy'], metrics['high_incongruent']['mean_rt'],
                    stroop_effects['high']
                ]
            }
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_csv(f"{prefix}_{summary_data_file}", index=False)
            
            return metrics, stroop_effects
    
    return None, None

def generate_block_sequence():
    # Separate all blocks
    stroop_blocks = [b for b in block_definitions if b['type'] != 'neutral']
    neutral_blocks = [b for b in block_definitions if b['type'] == 'neutral']
    
    # Shuffle stroop blocks with contrast repeat limits
    shuffled_stroop = []
    last_contrast = None
    contrast_counter = 0
    remaining_stroop = stroop_blocks.copy()
    
    while remaining_stroop:
        # Filter available blocks
        available = []
        for b in remaining_stroop:
            if b['contrast'] != last_contrast:
                available.append(b)
            else:
                if contrast_counter < 2:  # Allow up to 2 repeats
                    available.append(b)
        
        if not available:
            # Force contrast change if no valid options
            available = [b for b in remaining_stroop if b['contrast'] != last_contrast]
            
        chosen = random.choice(available)
        shuffled_stroop.append(chosen)
        remaining_stroop.remove(chosen)
        
        # Update contrast tracking
        if chosen['contrast'] == last_contrast:
            contrast_counter += 1
        else:
            last_contrast = chosen['contrast']
            contrast_counter = 1
    
    # Randomly insert neutral blocks (25% chance after each stroop block)
    sequence = []
    for block in shuffled_stroop:
        sequence.append(block)
        if neutral_blocks and random.random() < 0.25:
            sequence.append(random.choice(neutral_blocks))
    
    # Debug print
    print("\nGenerated Block Sequence:")
    for i, blk in enumerate(sequence, 1):
        print(f"{i}. {blk['type'].upper()} ({blk.get('contrast', 'neutral')})")
    
    return sequence

# Experiment instructions
instructions1 = visual.TextStim(win, text="Welcome to the Stroop Task!\n\nIn this task, you will see color words presented in different colors.\n\nYour task is to respond to the COLOR of the text, not the word itself.\n\nPress space to continue. (Press escape at any time to exit)", color="white", wrapWidth=700)
instructions1.draw()
win.flip()
event.waitKeys(keyList=["space", "escape"])
if event.getKeys(keyList=["escape"]):
    win.close()
    core.quit()

instructions2 = visual.TextStim(win, text="Press:\nR = Red\nG = Green\nB = Blue\nY = Yellow\n\nYou will complete a full version with different conditions in them.\n\nThere will be neutral screens between blocks.\n\nPress space to start. (Press escape at any time to exit)", color="white", wrapWidth=700)
instructions2.draw()
win.flip()
event.waitKeys(keyList=["space", "escape"])
if event.getKeys(keyList=["escape"]):
    win.close()
    core.quit()
    
send_event_code(outlet, 0, 'experiment_start')

def create_stroop_stimulus(stimulus_code, contrast):
    for color_name in ["red", "green", "blue", "yellow"]:
        if stimulus_code.startswith(color_name):
            word = color_name
            color = stimulus_code[len(word):] or word
            break
    
    colors = color_schemes[contrast]
    
    # For high contrast, ensure colors are vivid
    if contrast == 'high':
        return visual.TextStim(
            win,
            text=stroop_text[word],
            color=colors[color],
            height=80,
            bold=True,
            pos=[0, 0],
            colorSpace='rgb',
            opacity=1.0
        )
    else:  # low contrast
        return visual.TextStim(
            win,
            text=stroop_text[word],
            color=colors[color],
            height=80,
            bold=True,
            pos=[0, 0],
            colorSpace='rgb',
            opacity=0.1
        )

def run_block(block_def, block_num):
    """Run a single block with proper trial sampling and LSL markers"""
    # ===== 1. Handle Neutral Blocks =====
    if block_def['type'] == 'neutral':
        send_event_code(outlet, 300 + block_num, f'neutral_block_{block_num}_start')
    
        # Clear screen and draw neutral stimulus
        background.draw()
        neutral_stim = visual.TextStim(win, text="◯", color="white", height=40)  # Increased size
        neutral_stim.draw()
        win.flip()
    
        duration = random.uniform(18, 22)  # 18-22s neutral duration
        start_time = core.getTime()
    
        while core.getTime() - start_time < duration:
            check_for_escape()
            core.wait(0.1)
    
        send_event_code(outlet, 350 + block_num, f'neutral_block_{block_num}_end')
        return [{
            "participant": exp_info['participant'],
            "session": exp_info['session'],
            "block": block_num,
            "block_type": "neutral",
            "contrast": "n/a",
            "stimulus": "◯",  # Explicitly log the circle
            "response": "n/a",
            "correct": "n/a",
            "rt": duration
    }]

    # ===== 2. Stroop Block Setup =====
    # Get trial count (8 or 15)
    num_trials = block_def.get('trials', 8)  
    
    # Select appropriate trials
    trials = conditions[conditions["congruent"] == (1 if block_def['type'] == 'congruent' else 0)].copy()
    
    # Sample trials with replacement (ensures we get enough even if num_trials > unique trials)
    block_trials = trials.sample(n=num_trials, replace=True).to_dict('records')
    
    # ===== 3. Block-Level Markers =====
    code_prefix = 100 if block_def['contrast'] == 'low' else 200
    send_event_code(outlet, code_prefix + block_num, 
                   f"{block_def['contrast']}_{block_def['type']}_block_{block_num}_start")
    
    # ===== 4. Run Trials =====
    block_results = []
    prev_stimulus = None
    for trial_num, trial in enumerate(block_trials, 1):
        resample_attempts = 0
        while trial['stimulus'] == prev_stimulus and resample_attempts < 5:
            trial = trials.sample(1).iloc[0].to_dict()
            resample_attempts += 1
        prev_stimulus = trial['stimulus']

        
        # --- 4.2 Fixation ---
        background.draw()
        fixation.draw()
        win.flip()
        core.wait(0.5)
        check_for_escape()
        
        # --- 4.3 Blank Screen ---
        background.draw()
        win.flip()
        core.wait(0.1)
        
        # --- 4.4 Stimulus + LSL Marker ---
        send_event_code(outlet, code_prefix + 10 + trial_num, 
                       f"trial_{trial_num}_start_{trial['stimulus']}")
        
        stim = create_stroop_stimulus(trial['stimulus'], block_def['contrast'])
        background.draw()
        stim.draw()
        win.flip()
        
        # --- 4.5 Response Collection ---
        clock = core.Clock()
        keys = event.waitKeys(
            maxWait=2.0,
            keyList=["r", "g", "b", "y", "escape"],
            timeStamped=clock
        )
        
        # --- 4.6 Process Response ---
        if keys and keys[0][0] == 'escape':
            save_data(results, "partial")
            win.close()
            core.quit()
            
        if keys:
            key, rt = keys[0]
            correct = (key == trial['correct_response'])
            response_code = code_prefix + (30 if correct else 40) + trial_num
            send_event_code(outlet, response_code, f'response_{key}_{"correct" if correct else "incorrect"}')
        else:
            key, rt, correct = "None", 2.0, False
            send_event_code(outlet, code_prefix + 50 + trial_num, 'no_response')
        
        # --- 4.7 ITI ---
        background.draw()
        win.flip()
        core.wait(random.uniform(0.8, 1.2))
        check_for_escape()
        
        # --- 4.8 Save Trial Data ---
        block_results.append({
            "participant": exp_info['participant'],
            "session": exp_info['session'],
            "block": block_num,
            "block_type": block_def['type'],
            "contrast": block_def['contrast'],
            "stimulus": trial['stimulus'],
            "response": key,
            "correct": correct,
            "rt": rt
        })
    
    # ===== 5. Block End Marker =====
    send_event_code(outlet, code_prefix + 60 + block_num,
                   f"{block_def['contrast']}_{block_def['type']}_block_{block_num}_end")
    
    return block_results

# Generate random sequence
block_sequence = generate_block_sequence()
print(f"Generated block sequence with {len(block_sequence)} blocks")

# Run all blocks
for block_num, block_def in enumerate(block_sequence, 1):
    # Send block start marker
    if block_def['type'] != 'neutral':
        code_prefix = 100 if block_def['contrast'] == 'low' else 200
        send_event_code(outlet, code_prefix + block_num, 
                       f"{block_def['contrast']}_{block_def['type']}_start")
    
    # Run the block
    results.extend(run_block(block_def, block_num))
    
    # Send block end marker
    if block_def['type'] != 'neutral':
        send_event_code(outlet, code_prefix + 50 + block_num,
                       f"{block_def['contrast']}_{block_def['type']}_end")

# Display final feedback
metrics, stroop_effects = save_data(results)

# Display final feedback
if metrics and stroop_effects:
    feedback_text = (
        "Performance Results:\n\n"
        "LOW CONTRAST:\n"
        f"Congruent RT: {metrics['low_congruent']['mean_rt']:.3f}s\n"
        f"Incongruent RT: {metrics['low_incongruent']['mean_rt']:.3f}s\n"
        f"Stroop Effect: {stroop_effects['low']:.3f}s\n\n"
        "HIGH CONTRAST:\n"
        f"Congruent RT: {metrics['high_congruent']['mean_rt']:.3f}s\n"
        f"Incongruent RT: {metrics['high_incongruent']['mean_rt']:.3f}s\n"
        f"Stroop Effect: {stroop_effects['high']:.3f}s\n\n"
        "Press space to exit."
    )
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