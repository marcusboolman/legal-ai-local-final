"""
workers/asr_transcribe.py
- Transcribe audio/video using faster-whisper (CPU/GPU).
- Requires ffmpeg available in container.
- Writes SRT and JSON to /data/cases/<case_id>/parsed/asr/
"""
import os, sys, json, subprocess
from faster_whisper import WhisperModel

def extract_audio(input_path, out_wav):
    subprocess.run(["ffmpeg","-y","-i",input_path,"-ar","16000","-ac","1",out_wav], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main(case_id):
    assets = f"/data/cases/{case_id}/assets"
    out_dir = f"/data/cases/{case_id}/parsed/asr"
    os.makedirs(out_dir, exist_ok=True)
    model = WhisperModel("medium", device="auto", compute_type="auto")
    for name in os.listdir(assets):
        if not name.lower().endswith((".mp3",".wav",".m4a",".mp4",".mov",".mkv")):
            continue
        src = os.path.join(assets, name)
        wav = os.path.join(out_dir, name + ".wav")
        extract_audio(src, wav)
        segments, info = model.transcribe(wav, language="zh")
        srt_path = os.path.join(out_dir, name + ".srt")
        json_path = os.path.join(out_dir, name + ".json")
        # write srt
        def fmt_time(t):
            ms = int((t - int(t)) * 1000)
            h = int(t // 3600); m = int((t % 3600)//60); s = int(t % 60)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
        with open(srt_path, "w", encoding="utf-8") as srt:
            for i, seg in enumerate(segments, start=1):
                srt.write(f"{i}\n{fmt_time(seg.start)} --> {fmt_time(seg.end)}\n{seg.text.strip()}\n\n")
        # write json
        with open(json_path, "w", encoding="utf-8") as jf:
            jf.write(json.dumps({"source": name, "segments":[{"start":seg.start,"end":seg.end,"text":seg.text} for seg in segments]}, ensure_ascii=False, indent=2))
        print(f"[ok] ASR -> {srt_path}")
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python workers/asr_transcribe.py <case_id>")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
