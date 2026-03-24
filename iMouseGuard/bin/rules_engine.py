#!/usr/bin/env python3
"""
Behavioral Rules Engine for iMouseGuard
Evaluates mouse behavior patterns based on research questions.
"""

import json
import os
import sys
import time
from pathlib import Path

# ============ CONFIG ============

STATE_DIR = Path(__file__).parent.parent / "state"
STATE_FILE = STATE_DIR / "rules_state.json"
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_FILE = LOG_DIR / "rules.log"

def ensure_dirs():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)

ensure_dirs()

# ============ LOGGING ============

def log(msg):
    """Log to rules.log"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[RULES] {timestamp} | {msg}\n")
            f.flush()
    except:
        pass

def log_rule(rule_name, status, message):
    """Log rule evaluation"""
    log(f"{rule_name:30} | {status:10} | {message}")

# ============ STATE MANAGEMENT ============

def load_state():
    """Load zone activity state from disk"""
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        log(f"STATE load error: {e}")
    
    return {
        "zones": {},  # zone_id -> last_activity_timestamp
        "cooldowns": {},  # rule_ID -> cooldown_end_timestamp
        "house_entry_time": None,  # timestamp when entered house zone
        "drink_events": []  # list of (timestamp, zone_id)
    }

def save_state(state):
    """Save zone activity state to disk"""
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp_file = STATE_FILE.parent / (STATE_FILE.name + ".tmp")
        with open(tmp_file, "w") as f:
            json.dump(state, f, indent=2)
        tmp_file.replace(STATE_FILE)
    except Exception as e:
        log(f"STATE save error: {e}")

def get_env(key, default=""):
    """Get environment variable"""
    return os.environ.get(key, default)

# ============ BEHAVIORAL RULES ============

class BehavioralRules:
    """
    4 behavioral rules based on research questions:
    1. LITTER_ABSENCE - Has mouse failed to visit litter zone for unusually long?
    2. DRINKING_ABNORMAL - Concerning drinking inactivity or overuse?
    3. ACTIVITY_PATTERN_CHANGE - Unusual activity during sleep hours?
    4. HOUSE_ZONE_OCCUPANCY - Extended house/nest zone occupancy?
    """
    
    @staticmethod
    def litter_absence(event, state):
        """
        Q1: Has mouse failed to litter zone for unusually long?
        Threshold: 5+ minutes no litter zone activity
        Cooldown: 10 minutes
        Zone: 5 = Litter
        """
        rule_id = "LITTER_ABSENCE"
        
        # Check cooldown
        cooldown_end = state.get("cooldowns", {}).get(rule_id, 0)
        if time.time() < cooldown_end:
            log_rule(rule_id, "COOLDOWN", f"Cooldown until {time.ctime(cooldown_end)}")
            return None
        
        zone_id = event.get("zone_id")
        if zone_id != 5:  # Zone 5 = Litter
            return None
        
        # Update last activity time for this zone
        state.setdefault("zones", {})[5] = time.time()
        save_state(state)
        
        # Only alert if we see non-litter activity after litter was idle
        last_litter = state.get("zones", {}).get(5, time.time())
        idle_minutes = (time.time() - last_litter) / 60.0
        
        if idle_minutes >= 5:  # 5+ minute threshold
            state["cooldowns"][rule_id] = time.time() + (10 * 60)  # 10 min cooldown
            save_state(state)
            
            return {
                "rule": rule_id,
                "message": f"🐭 Litter absence alert: No activity for {idle_minutes:.1f} minutes"
            }
        
        return None
    
    @staticmethod
    def drinking_abnormal(event, state):
        """
        Q2: Concerning drinking inactivity or overuse?
        Type A - Inactivity: 1hr+ no water zone activity
        Type B - Overuse: 10+ events in short period
        Threshold: 1 hour OR 10+ events
        Cooldown: 30 minutes
        Zone: 4 = Water/Drinking
        """
        rule_id = "DRINKING_ABNORMAL"
        
        # Check cooldown
        cooldown_end = state.get("cooldowns", {}).get(rule_id, 0)
        if time.time() < cooldown_end:
            log_rule(rule_id, "COOLDOWN", f"Cooldown until {time.ctime(cooldown_end)}")
            return None
        
        zone_id = event.get("zone_id")
        
        # Track drinking zone activity
        now = time.time()
        drink_events = state.get("drink_events", [])
        # Remove events older than 1 hour
        drink_events = [ts for ts in drink_events if now - ts < 3600]
        
        if zone_id == 4:  # Water zone
            drink_events.append(now)
            state["drink_events"] = drink_events
            save_state(state)
        
        # Check Type B: Overuse (10+ events)
        if len(drink_events) >= 10:
            state["cooldowns"][rule_id] = time.time() + (30 * 60)  # 30 min cooldown
            drink_events.clear()
            state["drink_events"] = drink_events
            save_state(state)
            
            return {
                "rule": rule_id,
                "message": f"💧 Drinking overuse detected: {len(drink_events)} events in 1 hour"
            }
        
        # Check Type A: Inactivity (1hr+ no water activity)
        last_drink = state.get("zones", {}).get(4)
        if last_drink:
            idle_minutes = (now - last_drink) / 60.0
            if idle_minutes >= 60:  # 1 hour threshold
                state["cooldowns"][rule_id] = time.time() + (30 * 60)  # 30 min cooldown
                save_state(state)
                
                return {
                    "rule": rule_id,
                    "message": f"💧 Drinking inactivity: No water zone activity for {idle_minutes:.0f} minutes"
                }
        
        return None
    
    @staticmethod
    def activity_pattern_change(event, state):
        """
        Q3: Are activity patterns normal? Unusual activity during sleep?
        Trigger: High score (>80) during sleep hours (8PM-6AM)
        Cooldown: 1 hour
        Interpretation: Stress, pain, or environmental change
        """
        rule_id = "ACTIVITY_PATTERN_CHANGE"
        
        # Check cooldown
        cooldown_end = state.get("cooldowns", {}).get(rule_id, 0)
        if time.time() < cooldown_end:
            log_rule(rule_id, "COOLDOWN", f"Cooldown until {time.ctime(cooldown_end)}")
            return None
        
        score = event.get("score", 0)
        if score < 80:  # Only high activity
            return None
        
        # Check if in sleep hours (8 PM to 6 AM)
        hour = time.localtime().tm_hour
        is_sleep_hours = (hour >= 20) or (hour < 6)  # 8 PM to 6 AM
        
        if is_sleep_hours:
            state["cooldowns"][rule_id] = time.time() + (60 * 60)  # 1 hour cooldown
            save_state(state)
            
            return {
                "rule": rule_id,
                "message": f"🌙 Unusual activity during sleep hours (score: {score})"
            }
        
        return None
    
    @staticmethod
    def house_zone_occupancy(event, state):
        """
        Q4: Is nest time normal? Too long inside?
        Trigger: 2+ hours in house/nest zone (zone 3)
        Cooldown: 15 minutes
        Question: Extended occupancy might indicate illness or stress
        """
        rule_id = "HOUSE_ZONE_OCCUPANCY"
        
        # Check cooldown
        cooldown_end = state.get("cooldowns", {}).get(rule_id, 0)
        if time.time() < cooldown_end:
            log_rule(rule_id, "COOLDOWN", f"Cooldown until {time.ctime(cooldown_end)}")
            return None
        
        zone_id = event.get("zone_id")
        now = time.time()
        
        if zone_id == 3:  # House/nest zone
            # First time entering house
            if not state.get("house_entry_time"):
                state["house_entry_time"] = now
                save_state(state)
                return None
            
            # Check occupancy duration
            occupancy_minutes = (now - state["house_entry_time"]) / 60.0
            
            if occupancy_minutes >= 120:  # 2+ hour threshold
                state["cooldowns"][rule_id] = time.time() + (15 * 60)  # 15 min cooldown
                state["house_entry_time"] = None  # Reset entry time
                save_state(state)
                
                return {
                    "rule": rule_id,
                    "message": f"🏠 Extended house occupancy: {occupancy_minutes:.0f} minutes in nest"
                }
        else:
            # Mouse left house zone
            state["house_entry_time"] = None
            save_state(state)
        
        return None

# ============ MAIN EVALUATION ============

def evaluate_rules(event):
    """
    Main entry point: Evaluate all rules for an event
    Returns: {rule, message} or None
    """
    try:
        state = load_state()
        
        # Check each rule in order
        result = BehavioralRules.litter_absence(event, state)
        if result:
            log_rule(result["rule"], "TRIGGERED", result["message"])
            return result
        
        result = BehavioralRules.drinking_abnormal(event, state)
        if result:
            log_rule(result["rule"], "TRIGGERED", result["message"])
            return result
        
        result = BehavioralRules.activity_pattern_change(event, state)
        if result:
            log_rule(result["rule"], "TRIGGERED", result["message"])
            return result
        
        result = BehavioralRules.house_zone_occupancy(event, state)
        if result:
            log_rule(result["rule"], "TRIGGERED", result["message"])
            return result
        
        return None
    except Exception as e:
        log_rule("ERROR", "FAILED", str(e))
        return None

# ============ FOR COMMAND-LINE TESTING ============

if __name__ == "__main__":
    # Test with sample events: python rules_engine.py '{"meta": {"zone_id": 5, "score": 85}}'
    if len(sys.argv) > 1:
        try:
            event = json.loads(sys.argv[1])
            result = evaluate_rules(event)
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
