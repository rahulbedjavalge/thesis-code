# 📏 Behavioral Rules & Thresholds

**Rule Definitions, Thresholds & Implementation Guide**

---

## Overview

The rules engine evaluates incoming events against configurable behavioral thresholds to determine if an alert should be triggered. This document defines all behavioral rules, their detection logic, and tuning parameters.

---

## 🎯 Rule Structure

Each rule follows this template:

```python
{
    'name': 'RULE_NAME',
    'description': 'What this rule detects',
    'condition': 'Expression evaluated against event data',
    'severity': 'INFO | WARNING | CRITICAL',
    'cooldown_sec': 600,  # Prevent alert spam
    'enabled': True,
    'actions': ['telegram', 'slack', 'whatsapp'],
    'thresholds': {
        'ACTIVE': {...},
        'SLEEP': {...},
        'HYPER_ACTIVE': {...}
    }
}
```

---

## 📋 Implemented Rules

### 1. LITTER_ABSENCE

**Description:** Mouse activity in primary litter zone suddenly stops

**Trigger Condition:**
- Zone 5 (Litter) has no detected motion for > 5 minutes
- During ACTIVE window
- Motion previously detected in last 30 minutes

**Thresholds:**

| Parameter | ACTIVE | SLEEP | HYPER_ACTIVE |
|-----------|--------|-------|--------------|
| Idle time (sec) | 300 | 900 | 180 |
| Cooldown (sec) | 600 | 1800 | 300 |
| Min confidence | 70% | 60% | 75% |
| Severity | WARNING | INFO | CRITICAL |

**Implementation:**

```python
LITTER_ABSENCE = {
    'condition': '''
        zone_idle_seconds(zone_id=5) > THRESHOLD.idle_time
        AND last_activity_zone(5) within 30 minutes
        AND current_window == "ACTIVE"
    ''',
    'severity': 'WARNING',
    'cooldown_sec': 600,
    'parameters': {
        'zone_id': 5,
        'idle_threshold': 300,  # seconds
        'lookback_minutes': 30,
        'min_confidence': 0.7
    }
}
```

**False Positive Mitigation:**
- Requires sustained (5+ min) idle, not momentary pause
- Checks recent activity history (last 30 min)
- Skips during SLEEP window (lower monitoring intensity)
- Cooldown prevents duplicate alerts within 10 minutes

**Tuning Tips:**
- ↑ `idle_threshold` if false positives occur (mouse rests frequently)
- ↓ `idle_threshold` for more sensitive detection
- Adjust `min_confidence` based on camera quality/lighting

### 2. DRINKING_INACTIVITY

**Description:** No activity detected at water station zone for prolonged period

**Trigger Condition:**
- Zone 4 (Water/Food) has no motion for > 1 hour
- During ACTIVE window
- After minimum 2 baseline detection events

**Thresholds:**

| Parameter | ACTIVE | SLEEP | HYPER_ACTIVE |
|-----------|--------|-------|--------------|
| Idle time (sec) | 3600 | 7200 | 1800 |
| Cooldown (sec) | 7200 | 14400 | 3600 |
| Min events | 2 | 1 | 3 |
| Severity | INFO | INFO | WARNING |

**Implementation:**

```python
DRINKING_INACTIVITY = {
    'condition': '''
        zone_idle_seconds(zone_id=4) > THRESHOLD.idle_time
        AND zone_event_count(4, last_24h) >= min_baseline_events
        AND current_window == "ACTIVE"
    ''',
    'severity': 'INFO',
    'cooldown_sec': 7200,
    'parameters': {
        'zone_id': 4,
        'idle_threshold': 3600,  # 1 hour
        'min_baseline_events': 2,
        'lookback_hours': 24
    }
}
```

**Detection Logic:**
1. Requires baseline of ≥ 2 drinking events in last 24 hours
2. Triggers only if currently in ACTIVE window
3. 1-hour idle + baseline activity = likely health concern
4. 2-hour cooldown to avoid spam

**False Positive Mitigation:**
- Requires baseline activity pattern (no alerts first 24h)
- Checks recent history to distinguish from new enclosure
- Information-level severity (not critical)
- Long cooldown (2 hours) for behavioral patterns

**Tuning Tips:**
- Monitor actual drinking frequency to set baseline
- Increase idle threshold for mice with irregular patterns
- Lower for animals with strict hydration needs

### 3. HOUSE_MOVED

**Description:** Detected displacement or relocation of mouse habitat/cage

**Trigger Condition:**
- Zone layout/geometry changes detected
- Baseline zone positions differ from current positions by > 15%
- Multiple zones show correlated displacement

**Thresholds:**

| Parameter | Value |
|-----------|-------|
| Position change threshold (%) | 15% |
| Min zones affected | 2 |
| Cooldown (sec) | 3600 |
| Severity | CRITICAL |

**Implementation:**

```python
HOUSE_MOVED = {
    'condition': '''
        SUM(zone_center_shift_pct > 15% for each zone) >= 2
        AND correlation(zone_shifts) > 0.8
    ''',
    'severity': 'CRITICAL',
    'cooldown_sec': 3600,
    'parameters': {
        'position_change_threshold_pct': 15,
        'min_zones_affected': 2,
        'min_correlation': 0.8
    }
}
```

**Detection Logic:**
1. Baseline zone centroids are stored from first 24 hours
2. Compares current zone centroids to baseline
3. If multiple zones shift in similar direction = likely cage move
4. Correlation check confirms coordinated shift (not random)

**False Positive Mitigation:**
- Requires ≥ 2 zones to show shift (filters single-zone noise)
- Correlation check (0.8+) ensures coordinated movement
- 1-hour cooldown (single event, not repeating)
- Critical severity for human review

**Tuning Tips:**
- Baseline comparison should exclude first 24h (learning period)
- Adjust threshold based on camera calibration precision
- Consider seasonal camera adjustments (lighting changes, etc.)

### 4. HYPERACTIVITY

**Description:** Excessive motion detected indicating stress or agitation

**Trigger Condition:**
- Event frequency > 60 events/hour
- OR: Zone-switching rate > 8 switches/minute
- DURING SLEEP window (abnormal)

**Thresholds:**

| Parameter | Value |
|-----------|-------|
| Events per hour | 60 |
| Zone switches per minute | 8 |
| Time window | 10 minutes |
| Severity | WARNING |
| Cooldown | 600 seconds |

**Implementation:**

```python
HYPERACTIVITY = {
    'condition': '''
        (event_rate_per_hour > 60 OR zone_switch_rate > 8_per_min)
        AND current_window == "SLEEP"
    ''',
    'severity': 'WARNING',
    'cooldown_sec': 600,
    'parameters': {
        'event_rate_threshold': 60,  # events/hour
        'zone_switch_threshold': 8,  # switches/minute
        'window_size_minutes': 10,
        'monitor_during': ['SLEEP']  # Flag unusual sleep activity
    }
}
```

**Detection Logic:**
1. Calculates event rate over 10-minute sliding window
2. Counts zone transitions (e.g., litter→food→litter)
3. Triggers if rate exceeds thresholds during SLEEP period
4. Normal daytime activity doesn't trigger (despite high rate)

**Behavioral Interpretation:**
- High activity during sleep = stress indicator
- Excessive zone switching = agitation or pain
- May indicate health issue, environmental stress, or predator

**False Positive Mitigation:**
- Only triggers during SLEEP window (not playful daytime activity)
- Sliding window smooths transient spikes
- 10-minute observation window confirms pattern
- Warning level (not critical) for investigation

**Tuning Tips:**
- Baseline first 1 week of normal behavior to establish rates
- Adjust thresholds based on species typical activity patterns
- Consider seasonal/circadian changes
- Correlate with external events (light, temperature, etc.)

---

## 🔄 Activity Windows

Define activity windows in configuration to adjust thresholds by time:

```yaml
activity_windows:
  ACTIVE:
    start: "09:00"
    end: "20:00"
    timezone: "Europe/Berlin"
    description: "Primary activity period (daytime)"

  SLEEP:
    start: "20:00"
    end: "09:00"
    timezone: "Europe/Berlin"
    description: "Rest period (night)"

  HYPER_ACTIVE:
    start: "17:00"
    end: "22:00"
    timezone: "Europe/Berlin"
    description: "Elevated activity period (early night)"
```

**Purpose:**
- Apply different thresholds based on time of day
- Avoid false positives during expected activity fluctuations
- Account for circadian rhythm variations

---

## 🚧 Rules Under Development

### LITTER_CORNER_PREFERENCE

**Concept:** Detect consistent corner preference in litter zone (indicates enclosure preference or health pattern)

**Status:** Planned  
**Trigger:** 80% of litter activity concentrated in 1 corner for 3+ days  
**Severity:** INFO (behavioral tracking)

### FOOD_HOARDING

**Concept:** Detect food accumulation behavior (possible stress indicator)

**Status:** Planned  
**Trigger:** Rapid food zone entries (hoarding pattern) vs. normal consumption  
**Severity:** WARNING

### NEST_BUILDING

**Concept:** Detect nesting materials activity (preparation pattern)

**Status:** Planned  
**Trigger:** Specific motion signature in bedding area  
**Severity:** INFO (natural behavior)

### AGGRESSIVE_INTERACTION

**Concept:** Detect fighting or aggression patterns (if multiple animals)

**Status:** Future  
**Trigger:** Zone collision + high velocity motion  
**Severity:** CRITICAL

---

## 🛠️ Implementation in rules_engine.py

### Current Status

The `rules_engine.py` skeleton exists to host implementation:

```python
# bin/rules_engine.py

def evaluate(event: dict, rules: list) -> dict:
    """
    Evaluate event against all active rules.
    
    Args:
        event: Event data with zone_id, event_id, timestamps, scores
        rules: List of active rule definitions
    
    Returns:
        {
            'should_alert': bool,
            'severity': str,
            'rule_matched': str,
            'message': str,
            'actions': list
        }
    """
    for rule in rules:
        if check_cooldown(rule, event):
            continue
            
        if evaluate_condition(rule['condition'], event):
            return {
                'should_alert': True,
                'severity': rule['severity'],
                'rule_matched': rule['name'],
                'actions': rule['actions']
            }
    
    return {'should_alert': False}

def evaluate_condition(condition: str, event: dict) -> bool:
    """Evaluate rule condition expression against event."""
    pass

def check_cooldown(rule: dict, event: dict) -> bool:
    """Check if alert is in cooldown period."""
    pass

def zone_idle_seconds(zone_id: int) -> int:
    """Query state for zone idle time."""
    pass

def zone_event_count(zone_id: int, hours: int) -> int:
    """Count events in zone over time period."""
    pass
```

### Integration Points

1. **Hook directly calls rules_engine:**
   ```python
   # In imouse_hook_alert.py
   from rules_engine import evaluate
   
   decision = evaluate(event, RULES)
   if decision['should_alert']:
       send_alerts(event, decision['actions'])
   ```

2. **Rules stored in configuration:**
   ```yaml
   # In configuration.yml or separate rules.yml
   rules:
     - name: LITTER_ABSENCE
       enabled: true
       severity: WARNING
       # ...
   ```

3. **State management for cooldowns/tracking:**
   ```python
   # In state/rules.db or state/seen_events.json
   {
     "LITTER_ABSENCE": {
       "last_triggered": "2026-03-23T14:30:45Z",
       "event_id": 12345
     }
   }
   ```

---

## 📊 Testing & Tuning

### Baseline Collection

1. **Collect 24-48 hours of normal behavior**
   ```bash
   # All zones should show normal patterns
   python analysis/analyze_tsv.py baseline_events.tsv
   ```

2. **Calculate baseline statistics**
   - Average events/hour per zone
   - Peak hours
   - Zone transition frequencies

3. **Use statistics to set rule thresholds**

### Rule Testing

```bash
# Test a specific rule with sample event
python -c "
from bin.rules_engine import evaluate
from bin.imouse_hook_alert import RULES

test_event = {
    'zone_id': 5,
    'zone_idle_sec': 400,
    'current_window': 'ACTIVE'
}

result = evaluate(test_event, RULES)
print(result)
"
```

### Tuning Workflow

1. **Collect false positives:**
   ```bash
   grep "MISFIRE\|FALSE_POSITIVE" logs/hook.log
   ```

2. **Analyze event logs for those times**
   ```bash
   grep "2026-03-23 14:30" logs/ws_forwarder.log | head -20
   ```

3. **Adjust threshold and re-test**

4. **Repeat for 3-5 days to confirm**

---

## 🎓 References

### Related Documentation
- [OPERATIONS.md](OPERATIONS.md) - Deployment and monitoring
- [DEVELOPMENT.md](DEVELOPMENT.md) - Development setup and debugging
- [../README.md](../README.md) - Overall architecture

### Research Background
- Animal behavioral patterns and monitoring
- ZoneMinder event detection and confidence scoring
- Temporal pattern analysis for anomaly detection

---

**Last Updated:** March 23, 2026  
**Maintainer:** iMouseGuard Development Team  
**Status:** 4 rules implemented, 3 rules planned, 1+ rules under design
