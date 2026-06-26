# Audio Fixtures

- clear_vowel_12s.wav: ~12s voiced sustained vowel, happy path.
- below_floor_03s.wav: ~0.3s voiced sample, should trigger minimum duration guard.
- silence_3s.wav: ~3s digital silence, should trigger NaN/silence guard.
- noisy_background.wav: voiced sample with background noise, should not raise.
All fixtures are mono 16-bit PCM WAV at 16 kHz.
