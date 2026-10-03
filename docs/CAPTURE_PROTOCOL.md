# Capture protocol

For whoever holds the phone; no technical knowledge needed. Follow it word for word. It takes about 5 minutes per room.

## Before you start (2 minutes)

1. Switch all lights on, open the curtains, open every interior door fully, and turn ceiling fans off. Move people and pets out of the room.
2. On the iPhone, check for at least 10 GB of free space and at least 50 % battery.
3. Go to Settings → Camera → Formats and choose **Most Compatible**.
4. For a LiDAR scan you need an iPhone Pro with **Stray Scanner** installed from the App Store (it needs iOS 18.6 or later).

## LiDAR scan (iPhone Pro, Stray Scanner): 1–3 minutes per room

1. Stand in the doorway facing straight into the room, with the phone square to the far wall. Put a small piece of tape on the floor at your feet; this is the **start mark**.
2. Open Stray Scanner and tap record.
3. Walk slowly, at half your normal pace, about 1 m from the walls, with the phone at chest height.
4. Sweep each wall from floor to ceiling. Show every corner, and both sides of every door and window.
5. Stand in the middle of the room and point the phone **straight up at the ceiling** for 3 seconds.
6. Walk back to the start mark, face the same view for 5 seconds, and stop recording.
7. In Stray Scanner, share the recording as a zip (AirDrop, or Save to Files).

For several rooms, make **one continuous recording**. Start at a mark in the hallway, do steps 3–5 in each room in turn, pass doorways slowly, and finish back at the mark. Write down the order of the rooms.

## Photos (any iPhone): 4–8 per room

- Use the Camera app in Photo mode (not Portrait) with the 1× lens. Hold the phone **landscape**, at chest height.
- In each room, take one photo from each corner aimed at the opposite corner, so that two walls and the floor and ceiling edges are visible. Then take one photo of each doorway from inside the room, showing the whole door frame.
- Do the rooms one at a time, and note which photos belong to which room.

## Video (any iPhone): one walkthrough

- Use the Camera app in Video mode: 1×, 1080p at 30 fps, landscape, Action mode off.
- Follow the same path and pace as the LiDAR scan. Keep the lines where the walls meet the floor and the ceiling in view. Pass doorways slowly, and end where you started.

## Avoid

- Sending files over WhatsApp or other messaging apps. They compress the files and strip the data we need.
- Moving furniture, or people walking through, during a recording.
- Fast turns, running, or pointing at a bright window or a large mirror for more than a moment.

## Handing over

Use AirDrop, the Files app, a USB cable or Google Drive, and always send the original files:
- LiDAR: the Stray Scanner zip, unchanged.
- Photos: one folder per room, named after the room (for example `bedroom`).
- Video: the original `.MOV` file.

Tell us the room names and which of the three you recorded.

## For the operator (laptop)

| Capture | Put it here | Then run |
|---|---|---|
| LiDAR | Unzip into `data/captures/<id>/`, so it holds `odometry.csv`, `depth/`, `confidence/` and `rgb.mp4` | `housefloor run --capture data/captures/<id> --tier auto --out out/<id>` |
| Photos | `data/captures/<id>/rooms/<room>/photos/` | same |
| Video | `data/captures/<id>/` with the `.MOV` inside | same |
