"""
ChronicForge — Roast Engine  (Soldier Boy Edition)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Persona   : Soldier Boy — brutal, crude, 80s superhero energy
TTS       : Cartesia (primary) → ElevenLabs (fallback) → silent
LLM       : Groq llama3-70b for special events (level-up, end-of-day)
Templates : 200+ Soldier Boy lines, offline fallback always available
Storage   : every roast persisted to SQLite journal
"""

import os
import random
import threading
from typing import Callable, Optional

from core.database import Roast, SessionFactory

# ══════════════════════════════════════════════════════════════════════════════
#  TEMPLATE BANK — Soldier Boy persona
# ══════════════════════════════════════════════════════════════════════════════

ROASTS = {
    "strength_fail": [
        "What the fuck is this shit? You call that a workout, you weak little bitch?",
        "Back in my day we didn't skip leg day, we crushed Nazis. You soft cocksucker.",
        "Your muscles disappeared faster than my fucking patience.",
        "I fought superpowered Russians and you're struggling with 10-pound weights?",
        "Pathetic. Even the goddamn janitor at Vought lifts heavier than you.",
        "You skipped the gym again? Real original, pussy.",
        "The only heavy lifting you do is carrying around your fucking excuses.",
        "I've seen stronger guys in retirement homes, kid.",
        "Keep this up and you'll look like a fucking soy boy within a year.",
        "No training today. The enemies are training. You're not. Do the math.",
        "I blew up an entire fucking compound once. What did you do today? Nothing.",
    ],
    "intellect_fail": [
        "You didn't read a single fucking page? What a goddamn surprise.",
        "Back in my day men read books. You read tweets and cry about it.",
        "Your brain is deader than the Payback team.",
        "You got the attention span of a goldfish with ADHD.",
        "I blew up more people than the number of pages you've read this month.",
        "Smart people read. You're out here rotting your brain like a fucking loser.",
        "Incredible. You had all day and learned absolutely nothing. Impressive stupidity.",
        "The dumbest guy on Payback was still smarter than you today.",
    ],
    "charisma_fail": [
        "You talked to zero people again? What a fucking shock.",
        "Even I had better game in the 80s, and I was on coke half the time.",
        "You're not mysterious, you're just a socially retarded ghost.",
        "Women can smell weakness on you from across the street, kid.",
        "Keep hiding in your room and die alone. Real hero shit.",
        "I used to have entire stadiums cheering for me. You can't even text back.",
    ],
    "vitality_fail": [
        "You slept like shit again? No wonder you look like a walking corpse.",
        "4 hours of sleep and you're proud of yourself? Fucking adorable.",
        "Your body is a temple and you treat it like a goddamn war crime.",
        "Water? Never heard of her, huh tough guy?",
        "Keep this up and your body's gonna retire before your career does.",
        "I took more care of my body on a 72-hour combat mission than you do daily.",
        "Soldier Boy ran on 4 hours of sleep and adrenaline. You have no excuse.",
    ],
    "discipline_fail": [
        "You had one fucking job and you still fucked it up. Classic.",
        "Discipline? You wouldn't know it if it fucked you in the ass.",
        "Back in my day we didn't need motivation — we had balls.",
        "Another day of doing absolutely jack shit. Impressive.",
        "You're not lazy, you're a professional fucking disappointment.",
        "Future you is gonna hate your weak, spineless guts.",
        "I was disciplined enough to survive 40 years in Russian captivity. You can't wake up on time.",
        "The schedule existed. You looked at it. That was your only interaction.",
    ],
    "creativity_fail": [
        "You built nothing today. Created nothing. Contributed exactly jack shit.",
        "A real man makes things. You just consumed like a fucking leech.",
        "Even I had a brand. Soldier Boy meant something. What do you mean?",
        "Another day of zero output. Embarrassing.",
    ],
    "wealth_fail": [
        "Money doesn't make itself, dipshit. You have to actually do something.",
        "Broke and proud of it? That's the most pathetic combo I've ever seen.",
        "I had a Vought contract worth millions. What's your excuse?",
        "Your finances are a bigger disaster than my time in Nicaragua.",
    ],
    "general_fail": [
        "What a fucking waste of oxygen you are today.",
        "You're not in a slump, you're in a goddamn grave.",
        "Another day closer to dying with nothing to show for it.",
        "Pathetic. Even the Vought interns work harder than your sorry ass.",
        "You're a fucking disappointment, kid. Plain and simple.",
        "I expected more from you. Clearly that was my mistake.",
        "You wanna be a hero? Heroes don't have days like the one you just had.",
        "Soldier Boy didn't survive 40 years in a Russian lab so you could do nothing.",
    ],
}

PRAISE = {
    "strength": [
        "Finally did something right. About fucking time, kid.",
        "Now that's more like it. You actually trained like a man today.",
        "I'm almost impressed. Almost. Don't push it.",
        "That's how you build a body. Keep going and maybe you won't embarrass me.",
        "Soldier Boy respects the grind. Today you earned it.",
    ],
    "intellect": [
        "You actually read? Holy shit, pigs are flying today.",
        "Using your brain for once? I like this version of you.",
        "Knowledge is power. Today you got a little less stupid.",
        "Didn't think you had it in you. Turns out you do. Barely.",
    ],
    "charisma": [
        "You talked to actual humans today? Progress.",
        "Look at you, being social. I'm not moved, but it's noted.",
        "That's how you build a network, kid. Keep it up.",
    ],
    "vitality": [
        "Body maintained. Good. A broken-down soldier is useless.",
        "Sleep, water, clean food. You finally figured it out.",
        "The body is a weapon. Today you treated it like one.",
    ],
    "discipline": [
        "You actually did what you said you'd do. I'm shocked.",
        "Finally acting like a man instead of a whiny little bitch.",
        "Discipline separates heroes from civilians. Today you were a hero.",
        "You showed up. Soldier Boy always showed up. Now so did you.",
    ],
    "creativity": [
        "You built something today. That matters.",
        "Creation over consumption. That's how legends are made.",
        "Made something from nothing. Respect.",
    ],
    "wealth": [
        "Smart with money today. That's how empires are built.",
        "Every dollar tracked is a dollar working for you. Good move.",
        "Financial discipline is real discipline. You showed both today.",
    ],
    "general": [
        "You didn't completely suck today. I'll take the W.",
        "Not completely worthless. That's the nicest thing I'll say.",
        "Today was solid. Don't let it get to your head.",
        "You actually showed up. That's more than most people do.",
        "Progress logged. Soldier Boy approves. Barely.",
    ],
}

LEVEL_UP_LINES = [
    "Level {level}. You're finally starting to grow a pair.",
    "Level {level}. Don't let it go to your fucking head, kid.",
    "Level {level} achieved. About goddamn time.",
    "Level {level}. I've trained worse. Not by much, but still.",
    "Level {level}. Soldier Boy is watching. Don't waste it.",
]

STREAK_LINES = {
    3: "3 days straight. You're not a complete write-off after all.",
    7: "A full week. I've seen soldiers break faster. You didn't. Good.",
    14: "Two weeks of discipline. I'm starting to take you seriously.",
    30: "30 days. ONE MONTH. That's actual fucking commitment. Respect.",
    100: "100 days. That's not a streak, that's a goddamn identity. Soldier Boy salutes.",
    365: "365 days. A full year. You're not a civilian anymore. You're something else.",
}


# ══════════════════════════════════════════════════════════════════════════════
#  TTS — Cartesia (primary) → ElevenLabs (fallback)
# ══════════════════════════════════════════════════════════════════════════════


def _speak_soldier_boy(text: str, on_ready: Optional[Callable[[str], None]] = None):
    """
    Generate and play voice audio in a background thread.
    on_ready(text) fires when audio is loaded and about to play —
    sprite bubble appears exactly when speech starts.
    """
    cartesia_key = os.environ.get("CARTESIA_API_KEY", "")
    cartesia_voice = os.environ.get(
        "CARTESIA_VOICE_ID", "dded70d9-73b5-4c77-b76c-97e3c86a6705"
    )
    eleven_key = os.environ.get("ELEVENLABS_API_KEY", "")
    eleven_voice = os.environ.get("ELEVENLABS_VOICE_ID", "pNInz6obbfDQGcgMyIGb")

    # Ellipsis prefix → natural breath before speech (prevents abrupt TTS start)
    tts_text = f"... {text}"
    audio_data = None

    # ── Cartesia ──────────────────────────────────────────────────────────────
    if cartesia_key:
        try:
            import requests

            print(f"[Soldier Boy TTS] Cartesia...")
            resp = requests.post(
                "https://api.cartesia.ai/tts/bytes",
                headers={
                    "Cartesia-Version": "2024-06-10",
                    "X-API-Key": cartesia_key,
                    "Content-Type": "application/json",
                },
                json={
                    "model_id": "sonic-english",
                    "transcript": tts_text,
                    "voice": {"mode": "id", "id": cartesia_voice},
                    "output_format": {
                        "container": "wav",
                        "encoding": "pcm_s16le",
                        "sample_rate": 44100,
                    },
                },
                timeout=10,
            )
            if resp.status_code == 200:
                import io

                from pydub import AudioSegment

                audio_data = AudioSegment.from_file(
                    io.BytesIO(resp.content), format="wav"
                )
                print(f"[Soldier Boy TTS] Cartesia OK.")
            else:
                print(
                    f"[Soldier Boy TTS] Cartesia {resp.status_code}: {resp.text[:80]}"
                )
        except Exception as exc:
            print(f"[Soldier Boy TTS] Cartesia exception: {exc}")

    # ── ElevenLabs fallback ───────────────────────────────────────────────────
    if audio_data is None and eleven_key:
        try:
            import requests

            print(f"[Soldier Boy TTS] ElevenLabs fallback...")
            resp = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{eleven_voice}",
                headers={
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                    "xi-api-key": eleven_key,
                },
                json={
                    "text": tts_text,
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                },
                timeout=10,
            )
            if resp.status_code == 200:
                import io

                from pydub import AudioSegment

                audio_data = AudioSegment.from_file(
                    io.BytesIO(resp.content), format="mp3"
                )
                print(f"[Soldier Boy TTS] ElevenLabs OK.")
            else:
                print(
                    f"[Soldier Boy TTS] ElevenLabs {resp.status_code}: {resp.text[:80]}"
                )
        except Exception as exc:
            print(f"[Soldier Boy TTS] ElevenLabs exception: {exc}")

    # ── Playback ──────────────────────────────────────────────────────────────
    if audio_data is not None:
        # Fire sprite bubble BEFORE playback so text appears as speech starts
        if on_ready:
            on_ready(text)
        try:
            from pydub import AudioSegment
            from pydub.playback import play

            # 300ms silence → prevents BT headphone clip on driver wake
            play(AudioSegment.silent(duration=300) + audio_data)
            print(f"[Soldier Boy TTS] Finished.")
        except Exception as exc:
            print(f"[Soldier Boy TTS] Playback error: {exc}")
    else:
        # No audio — still show the bubble
        if on_ready:
            on_ready(text)
        print(f"[Soldier Boy] (silent) {text}")


# ══════════════════════════════════════════════════════════════════════════════
#  GROQ — dynamic lines for special events
# ══════════════════════════════════════════════════════════════════════════════

_groq_client = None


def _get_groq():
    global _groq_client
    if _groq_client is not None:
        return _groq_client
    try:
        from groq import Groq

        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            try:
                from config.settings import load_config

                api_key = load_config().ai.groq_api_key
            except Exception:
                pass
        if api_key:
            _groq_client = Groq(api_key=api_key)
            print("[ChronicForge] Groq client initialised.")
    except Exception as exc:
        print(f"[ChronicForge] Groq unavailable: {exc}")
    return _groq_client


def _groq_roast(char: dict, trigger: str, roast_type: str) -> Optional[str]:
    """Improved prompt for natural, flowing Soldier Boy voice"""
    client = _get_groq()
    if not client:
        return None

    stats_str = ", ".join(f"{k}: {v:.0f}" for k, v in char.get("stats", {}).items())

    prompt = f"""You are Soldier Boy from The Boys.
You are arrogant, crude, loud, toxic, and brutally honest with 1980s macho energy.
You swear naturally. You vary your sentences. You don't repeat the same phrases.
You sound like a real angry, cocky person — not a robot.

Good examples of how you talk:
- "What the fuck is this shit? You call that a workout, you weak little bitch?"
- "Back in my day we didn't skip leg day, we crushed Nazis. You soft cocksucker."
- "I fought superpowered Russians and you're struggling with 10-pound weights? Pathetic."
- "Finally did something right. About fucking time, kid. Don't get cocky."

Current stats: {stats_str}
Streak: {char.get("streak", 0)} days
Trigger: {trigger}
Type: {roast_type} (roast = savage insult, praise = grudging respect)

Write ONE natural, flowing line in Soldier Boy's voice.
Make it sound like a real person talking. Vary your wording.
Be creative with the insults. Max 24 words.
No quotes. No preamble. Just the line."""

    try:
        from config.settings import load_config

        model_name = load_config().ai.groq_model or "llama-3.3-70b-versatile"
    except Exception:
        model_name = "llama-3.3-70b-versatile"

    try:
        resp = _groq_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=75,
            temperature=0.92,
            top_p=0.95,
            frequency_penalty=0.7,
            presence_penalty=0.6,
        )
        text = resp.choices[0].message.content.strip().strip("\"'")
        return text if len(text) > 8 else None
    except Exception as exc:
        print(f"[ChronicForge] Groq error: {exc}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  TEMPLATE SELECTOR
# ══════════════════════════════════════════════════════════════════════════════


def _template_roast(
    roast_type: str, stat: Optional[str], trigger: str, char: dict
) -> str:
    if roast_type == "praise":
        pool = PRAISE.get(stat, PRAISE["general"]) if stat else PRAISE["general"]
        return random.choice(pool)

    if trigger == "levelled_up":
        return random.choice(LEVEL_UP_LINES).format(level=char.get("level", 1))

    if trigger.startswith("streak_"):
        n = char.get("streak", 0)
        for threshold in sorted(STREAK_LINES.keys(), reverse=True):
            if n >= threshold:
                return STREAK_LINES[threshold]

    if stat and f"{stat}_fail" in ROASTS:
        return random.choice(ROASTS[f"{stat}_fail"])

    return random.choice(ROASTS["general_fail"])


# ══════════════════════════════════════════════════════════════════════════════
#  PERSISTENCE
# ══════════════════════════════════════════════════════════════════════════════


def _save_roast(text: str, roast_type: str, trigger: str, source: str):
    try:
        with SessionFactory() as session:
            session.add(
                Roast(
                    character_id=1,
                    text=text,
                    roast_type=roast_type,
                    trigger=trigger,
                    source=source,
                )
            )
            session.commit()
    except Exception:
        pass


def get_roast_journal(limit: int = 20) -> list[dict]:
    from sqlalchemy import select

    with SessionFactory() as session:
        rows = session.scalars(
            select(Roast)
            .where(Roast.character_id == 1)
            .order_by(Roast.created_at.desc())
            .limit(limit)
        ).all()
        return [
            {
                "text": r.text,
                "type": r.roast_type,
                "trigger": r.trigger,
                "source": r.source,
                "date": r.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for r in rows
        ]


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

_GROQ_TRIGGERS = {
    "general",
    "levelled_up",
    "quest_done",
    "streak_milestone",
    "end_of_day",
}


def get_roast(
    trigger: str = "general",
    roast_type: str = "roast",
    use_groq: bool = True,
    stat: Optional[str] = None,
    speak: bool = True,
) -> Optional[str]:
    """
    Get a Soldier Boy roast or praise line.

    speak=True  → plays TTS async, fires event_bus.roast_ready when audio ready.
                  Returns None (non-blocking).
    speak=False → returns text immediately, no TTS (for CLI / display-only use).
    """
    char = {}
    try:
        from core.game_logic import get_character

        char = get_character()
    except Exception:
        pass

    # Pick text
    text = None
    source = "template"
    if use_groq and trigger in _GROQ_TRIGGERS:
        text = _groq_roast(char, trigger, roast_type)
        if text:
            source = "groq"
    if not text:
        text = _template_roast(roast_type, stat, trigger, char)

    _save_roast(text, roast_type, trigger, source)

    print(f"\n[Soldier Boy | {source.upper()}] {text}\n")

    if not speak:
        return text

    # Async TTS: bubble fires when audio is ready (synced to playback start)
    def _on_audio_ready(t: str):
        try:
            from utils.signals import event_bus

            event_bus.roast_ready.emit(t)
        except Exception:
            pass

    threading.Thread(
        target=_speak_soldier_boy,
        args=(text, _on_audio_ready),
        daemon=True,
    ).start()
    return None


def end_of_day_review() -> Optional[str]:
    """
    Soldier Boy end-of-day verdict. Calls Groq if available.
    Plays TTS aloud. Called once per day at midnight tick.
    """
    today_logs = []
    try:
        from datetime import date

        from core.game_logic import get_recent_logs

        today_logs = [
            l for l in get_recent_logs(1) if l["date"] == date.today().isoformat()
        ]
    except Exception:
        pass

    if not today_logs:
        return get_roast("end_of_day", "roast", use_groq=True, speak=True)

    stats_done = list({l["stat"] for l in today_logs})
    return get_roast(
        "end_of_day",
        "praise",
        use_groq=True,
        stat=stats_done[0] if stats_done else None,
        speak=True,
    )


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Soldier Boy Roast Engine — template test (no API keys needed)\n")
    for stat in ["strength", "intellect", "discipline", "creativity", "general"]:
        t = get_roast(stat=stat, roast_type="roast", speak=False)
        print(f"[roast / {stat:12s}] {t}")
    print()
    for stat in ["strength", "discipline", "general"]:
        t = get_roast(stat=stat, roast_type="praise", speak=False)
        print(f"[praise/ {stat:12s}] {t}")


# ══════════════════════════════════════════════════════════════════════════════
#  PROACTIVE REMARKS — time-aware, unprompted sprite one-liners
# ══════════════════════════════════════════════════════════════════════════════

_REMARKS = {
    "morning": [
        "Rise and grind, dipshit. Daylight's burning.",
        "Morning. Don't waste it like yesterday.",
        "New day. New chance to not be completely useless.",
        "Up early? Good. Now do something with it.",
        "Sun's up. Get to work before you lose your nerve.",
    ],
    "afternoon": [
        "Half the day's gone. What have you done with it?",
        "Afternoon check-in. Productive? Or just surviving?",
        "Still grinding or did you fold after lunch?",
        "Three o'clock. The weak ones nap. The strong ones push.",
        "How's the quest log looking? Don't say empty.",
    ],
    "evening": [
        "Evening. Log what you did before you forget and lie to yourself.",
        "Day's almost done. Make it count or admit defeat.",
        "The night belongs to those who earned it. Did you?",
        "Sundown. Time to review the damage.",
        "Before you zone out — did you log everything today?",
    ],
    "night_owl": [
        "It's past midnight. Soldier Boy judges this.",
        "2am? This better be because you were productive, not scrolling.",
        "The sleep deprivation is showing. Get to bed, idiot.",
        "Nothing good happens after midnight. Log your day and sleep.",
    ],
    "no_log_nudge": [
        "You haven't logged anything today. Fix that.",
        "The chronicle is empty today. Don't let the day die undocumented.",
        "Nothing logged yet. Either you did nothing, or you're slacking on records.",
        "Soldier Boy notices you haven't logged today. This is your one warning.",
    ],
    "streak_alive": [
        "Streak's still alive. Don't be the idiot who breaks it tonight.",
        "Keep the streak going. One day at a time.",
        "The streak is real. Don't fuck it up now.",
    ],
    "streak_danger": [
        "You haven't logged today and it's getting late. The streak dies if you sleep now.",
        "Log something. Anything. Before midnight kills the streak.",
        "Streak on the line. Clock's ticking. Move.",
    ],
    "idle_remark": [
        "Still here. Still watching. Don't get comfortable.",
        "You know what would be great? Doing something productive.",
        "I've fought actual supervillains. Your excuses don't impress me.",
        "Standing by. Not because I want to. Because someone has to watch over you.",
        "The quest board isn't going to complete itself.",
        "I blew up a city block once. You can't finish one task today?",
        "Every minute you waste is a minute your future self curses you for.",
    ],
    "stat_neglect": [
        "You haven't touched {stat} in over a week. Rot in mediocrity.",
        "{stat} collecting dust like your dreams. Typical.",
        "Seven days. Not one {stat} entry. You are the neglect.",
        "I've seen corpses with more active {stat} stats than you.",
        "Your {stat} is starving and you're out here living your best life. Pathetic.",
    ],
}


def proactive_remark(context: str = "idle", speak: bool = True) -> Optional[str]:
    """
    Generate a time/context-aware Soldier Boy one-liner for unprompted sprite remarks.
    context: 'morning' | 'afternoon' | 'evening' | 'night_owl' |
             'no_log_nudge' | 'streak_alive' | 'streak_danger' | 'idle'
    """
    pool = _REMARKS.get(context, _REMARKS["idle_remark"])
    text = random.choice(pool)
    _save_roast(text, "neutral", f"proactive_{context}", "template")

    print(f"\n[Soldier Boy | PROACTIVE] {text}\n")

    if not speak:
        return text

    def _on_ready(t: str):
        try:
            from utils.signals import event_bus

            event_bus.sprite_remark.emit(t)
        except Exception:
            pass

    threading.Thread(
        target=_speak_soldier_boy,
        args=(text, _on_ready),
        daemon=True,
    ).start()
    return None


def get_neglect_roast(stat: str, speak: bool = True) -> Optional[str]:
    """
    Get a Soldier Boy roast for a neglected stat.
    speak=True  → plays TTS async, fires event_bus.sprite_remark when audio ready.
                  Returns None (non-blocking).
    speak=False → returns text immediately, no TTS.
    """
    pool = _REMARKS["stat_neglect"]
    text = random.choice(pool).replace("{stat}", stat.upper())
    _save_roast(text, "roast", f"stat_neglect_{stat}", "template")

    print(f"\n[Soldier Boy | NEGLECT] {text}\n")

    if not speak:
        return text

    def _on_ready(t: str):
        try:
            from utils.signals import event_bus

            event_bus.sprite_remark.emit(t)
        except Exception:
            pass

    threading.Thread(
        target=_speak_soldier_boy,
        args=(text, _on_ready),
        daemon=True,
    ).start()
    return None
