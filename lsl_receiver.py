# Save this as lsl_receiver.py
# Save this as lsl_receiver.py
from pylsl import StreamInlet, resolve_byprop
import time
from datetime import datetime
import csv
import sys
from typing import Optional, Dict, List

class RobustStroopReceiver:
    def __init__(self):
        self.inlet: Optional[StreamInlet] = None
        self.session_start: float = 0
        self.data: List[Dict] = []
        self.last_code: Optional[str] = None
        self.last_code_time: float = 0
        self.pairing_window: float = 0.1  # seconds

    def connect_to_stream(self, timeout: float = 30) -> bool:
        """Establish connection to LSL stream with retries"""
        print(f"\n{'='*50}")
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Starting Stroop Receiver")
        print("Press Ctrl+C to stop\n")
        
        start_time = time.time()
        attempt = 0
        
        while time.time() - start_time < timeout:
            attempt += 1
            try:
                print(f"Attempt {attempt}: Resolving StroopMarkers stream...")
                streams = resolve_byprop('name', 'StroopMarkers', timeout=5)
                
                if streams:
                    self.inlet = StreamInlet(streams[0], max_buflen=360)
                    self.session_start = time.time()
                    print(f"\n✅ Connected to source: {streams[0].source_id()}")
                    print(f"Stream created at: {datetime.fromtimestamp(streams[0].created_at()).strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"{'='*50}\n")
                    return True
                
                print("No stream found. Retrying...")
                time.sleep(2)
                
            except KeyboardInterrupt:
                print("\n🔴 Stopped by user during connection")
                sys.exit(0)
            except Exception as e:
                print(f"⚠️ Connection error: {str(e)}")
                time.sleep(1)
        
        print(f"❌ Failed to connect after {timeout} seconds")
        return False

    def process_marker(self, marker: str, timestamp: float) -> Dict:
        """Categorize and extract metadata from markers"""
        elapsed = time.time() - self.session_start
        record = {
            'timestamp': timestamp,
            'local_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            'elapsed_seconds': elapsed,
            'marker_content': marker,
            'numeric_code': None,
            'trial_color': None,
            'response_key': None,
            'response_correct': None
        }

        # Handle CODE_ markers
        if marker.startswith('CODE_'):
            code = marker.replace('CODE_', '')
            self.last_code = code
            self.last_code_time = time.time()
            record.update({
                'marker_type': 'CODE',
                'numeric_code': code
            })
            return record

        # Pair with recent code if available
        paired_code = None
        if self.last_code and (time.time() - self.last_code_time) < self.pairing_window:
            paired_code = self.last_code
            self.last_code = None
            record['numeric_code'] = paired_code

        # Categorize marker type
        if 'trial_start_' in marker:
            record['marker_type'] = 'TRIAL'
            record['trial_color'] = next(
                (c for c in ['red', 'green', 'blue', 'yellow'] if c in marker),
                None
            )
        elif 'response_' in marker:
            parts = marker.split('_')
            record.update({
                'marker_type': 'RESPONSE',
                'response_key': parts[1] if len(parts) > 1 else None,
                'response_correct': 'correct' in marker
            })
        elif 'block_' in marker:
            record['marker_type'] = 'BLOCK'
        elif 'neutral_block' in marker:
            record['marker_type'] = 'NEUTRAL'
        elif marker in ['experiment_start', 'experiment_end']:
            record['marker_type'] = 'EXPERIMENT'
        else:
            record['marker_type'] = 'SYSTEM'

        return record

    def display_marker(self, record: Dict):
        """Color-coded console output"""
        colors = {
            'CODE': '\033[95m',      # Purple
            'TRIAL': '\033[94m',     # Blue
            'RESPONSE': '\033[92m',  # Green (correct) / Red (incorrect)
            'BLOCK': '\033[96m',     # Cyan
            'NEUTRAL': '\033[93m',   # Yellow
            'EXPERIMENT': '\033[1;97;45m'  # Bold white on purple
        }
        
        color = colors.get(record['marker_type'], '\033[93m')  # Default yellow
        if record['marker_type'] == 'RESPONSE':
            color = '\033[92m' if record['response_correct'] else '\033[91m'
        
        code_display = f"[{record['numeric_code']}] " if record['numeric_code'] else ""
        print(f"{color}{record['local_time']} {record['elapsed_seconds']:8.3f}s  "
              f"{record['marker_type']}: {code_display}{record['marker_content']}\033[0m")

    def save_data(self):
        """Save collected data with comprehensive headers"""
        if not self.data:
            print("No data to save")
            return
            
        filename = f"stroop_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        print(f"\n💾 Saving {len(self.data)} markers to {filename}")
        
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.data[0].keys())
            writer.writeheader()
            writer.writerows(self.data)
        
        # Print summary statistics
        trials = [d for d in self.data if d['marker_type'] == 'TRIAL']
        responses = [d for d in self.data if d['marker_type'] == 'RESPONSE']
        correct = sum(1 for r in responses if r['response_correct'])
        
        print("\n📊 Experiment Summary:")
        print(f"Total trials: {len(trials)}")
        print(f"Total responses: {len(responses)}")
        print(f"Accuracy: {correct/len(responses):.1%}" if responses else "No responses recorded")

    def run(self):
        """Main receiver loop with auto-recovery"""
        if not self.connect_to_stream():
            return
            
        try:
            while True:
                try:
                    # Get marker with timeout
                    sample, timestamp = self.inlet.pull_sample(timeout=1.0)
                    
                    if sample:
                        record = self.process_marker(sample[0], timestamp)
                        self.display_marker(record)
                        self.data.append(record)
                        
                except KeyboardInterrupt:
                    print("\n🛑 Stopping receiver...")
                    break
                    
                except Exception as e:
                    print(f"\n⚠️ Stream error: {str(e)} - attempting recovery...")
                    if not self.connect_to_stream(timeout=10):
                        print("❌ Failed to recover connection")
                        break
                        
        finally:
            self.save_data()
            if self.inlet:
                self.inlet.close_stream()
            print("\nReceiver shutdown complete")

if __name__ == "__main__":
    receiver = RobustStroopReceiver()
    receiver.run()