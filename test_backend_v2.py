import requests
import time
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_endpoint(method, endpoint, expected_status=200, **kwargs):
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, **kwargs)
        elif method == "POST":
            response = requests.post(url, **kwargs)
        
        if response.status_code != expected_status:
            print(f"❌ {method} {endpoint} failed: {response.status_code} - {response.text}")
            return None
        
        print(f"✅ {method} {endpoint} - OK")
        return response.json()
    except Exception as e:
        print(f"❌ {method} {endpoint} error: {e}")
        return None

def main():
    print("--- Testing HMC v2.1 Backend Refactor ---")
    
    # 1. Health
    health = test_endpoint("GET", "/health")
    if not health: sys.exit(1)
    
    # 2. Initial State
    state = test_endpoint("GET", "/player/state")
    print(f"Initial State: {state}")
    if state['state'] != "idle":
        print("⚠️ Warning: Initial state is not IDLE (might be previous run)")

    # 3. Play Album (Mock)
    # Use a known album ID if possible, or just a dummy one since Mock handles it?
    # Jellyfin client might fail if ID doesn't exist, even in Mock player mode, 
    # because main.py calls jellyfin.get_tracks FIRST.
    # So we need a valid Album ID.
    
    # Get Libraries -> Artist -> Album -> Play
    libraries = test_endpoint("GET", "/libraries")
    if not libraries: 
        print("Skipping playback test (no libraries)")
        sys.exit(0)
        
    lib_id = libraries[0]['id']
    artists = test_endpoint("GET", f"/library/{lib_id}/artists")
    if not artists:
        print("Skipping playback test (no artists)")
        sys.exit(0)
        
    artist_id = artists[0]['id']
    albums = test_endpoint("GET", f"/artist/{artist_id}/albums")
    if not albums:
        print("Skipping playback test (no albums)")
        sys.exit(0)
        
    album_id = albums[0]['id']
    print(f"Found Album: {album_id}")
    
    play_res = test_endpoint("POST", f"/play/album/{album_id}")
    print(f"Play Result: {play_res}")
    
    # 4. Check State (Playing)
    state = test_endpoint("GET", "/player/state")
    print(f"State after Play: {state}")
    if state['state'] not in ["playing", "loading"]:
        print("❌ State should be playing")
    
    # 5. Pause
    pause_res = test_endpoint("POST", "/player/pause")
    print(f"Pause Result: {pause_res}")
    if pause_res['state'] != "paused":
         print("❌ State should be paused")

    # 6. Resume
    resume_res = test_endpoint("POST", "/player/resume")
    print(f"Resume Result: {resume_res}")
    if resume_res['state'] != "playing":
         print("❌ State should be playing")

    # 7. Stop
    stop_res = test_endpoint("POST", "/player/stop")
    print(f"Stop Result: {stop_res}")
    if stop_res['state'] != "stopped":
         print("❌ State should be stopped")

if __name__ == "__main__":
    main()
