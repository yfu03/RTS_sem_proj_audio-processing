import pyaudio
from pydub import AudioSegment
from pydub.playback import play

#from filter import *

import wave
import numpy as np
import tkinter as tk
import threading
import time
import os
import matplotlib
from matplotlib import pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import noisereduce as nr
import pedalboard
from pedalboard import *
from pedalboard.io import AudioFile

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
FRAMES_PER_BUFFER = 1024

CANVAS_WIDTH = 200
CANVAS_HEIGHT = 100


class RecordingGUI:
  def __init__(self):
    self.root = tk.Tk()
    self.root.resizable(False, False)
    self.root.title('Audio Enhancer')
    img = tk.PhotoImage(file='icon.png')
    self.root.iconphoto(False, img)

    self.recent_recording = ''

    self.fig, self.ax = plt.subplots()
    self.ax.set_title("Audio Signal")
    self.ax.set_ylabel("Signal Wave")
    self.ax.set_xlabel("Time in sec")
    self.canvas = FigureCanvasTkAgg(self.fig)
    self.canvas.get_tk_widget().pack()

    #center_line = self.sine_graph.create_line(0, CANVAS_HEIGHT//2, CANVAS_WIDTH, CANVAS_HEIGHT//2, fill='blue')

    self.button = tk.Button(text="Enable Recording", command = self.click_record) 
    self.button.config(background="green")
    self.button.pack()

    self.label = tk.Label(text="00:00:00.000")
    self.label.pack()

    self.input_playback_file = tk.Text(height = 2, width = 25)
    self.input_playback_file.pack()
    self.playbackButton = tk.Button(text="Audio Playback", command = self.play_recording)
    self.playbackButton.pack()

    self.input_graph_file = tk.Text(height = 2, width = 25)
    self.input_graph_file.pack()
    GraphButton = tk.Button(text="Graph Audio", command = self.graph_audio)
    GraphButton.pack()

    self.input_effect_file = tk.Text(height = 2, width = 25)
    self.input_effect_file.pack()

    options = [
      "Reduce Background Noise",
      "Equalization",
      "Reverb"
    ]
    self.clicked = tk.StringVar()
    self.clicked.set("Reduce Background Noise")

    self.effect_menu = tk.OptionMenu(self.root, self.clicked, *options)
    self.effect_menu.pack()

    self.effect = tk.Button(text = "Enhance Audio" , command = self.select_filter)
    self.effect.pack()

    QuitButton = tk.Button(text="Quit", command = self.quit)
    QuitButton.pack()

    self.isRecording = False

    self.root.mainloop()
  
  def click_record(self):
    if self.isRecording:
      self.isRecording = False
      self.button.config(background="green")
    else:
      self.isRecording = True
      self.button.config(background="red")
      threading.Thread(target=self.record_audio).start()

  def record_audio(self):
    pa = pyaudio.PyAudio()
    info = pa.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    stream = pa.open(
      format=FORMAT,
      channels=CHANNELS,
      rate=RATE,
      input=True,
      input_device_index=4, #index 4 = blue snowball, index 6 = rtx
      frames_per_buffer=FRAMES_PER_BUFFER
    )

    #print('now recording audio')
    frames = []
    start_time = time.time()
    while self.isRecording:
      data = stream.read(FRAMES_PER_BUFFER)
      frames.append(data)
      elapsed_time = time.time() - start_time
      mill = (elapsed_time * 1000) % 1000
      sec = elapsed_time % 60
      min = sec // 60
      hour = min // 60
      self.label.config(text=f"{int(hour):02d}:{int(min):02d}:{int(sec):02d}.{int(mill):03d}")
    #print('press button again to STOP recording')
    stream.stop_stream()
    stream.close()
    pa.terminate()

    file_num = 1
    while os.path.exists(f"recording{file_num}.wav"):
      file_num += 1
    file_name = f"recording{file_num}.wav"
    self.recent_recording = file_name

    write_wave = wave.open(file_name, 'wb') #wb means write binary
    write_wave.setnchannels(CHANNELS)
    write_wave.setsampwidth(pa.get_sample_size(FORMAT))
    write_wave.setframerate(RATE)
    write_wave.writeframes(b''.join(frames))
    write_wave.close()

  def play_recording(self):
    file_name = self.input_playback_file.get("1.0", 'end-1c')
    play_audio = AudioSegment.from_file(file_name, format="wav")
    play(play_audio)
  
  
  def graph_audio(self):
    file_name = self.input_graph_file.get("1.0", 'end-1c')
    file = wave.open(file_name, 'rb')
    sample_freq = file.getframerate()
    n_samples = file.getnframes()
    signal_wave = file.readframes(-1)

    file.close()
    t_audio = n_samples / sample_freq
    signal_array = np.frombuffer(signal_wave, dtype=np.int16)

    times = np.linspace(0, t_audio, num = n_samples)
    #plt.figure(figsize=(15, 5))
    self.ax.plot(times, signal_array)
    #plt.xlim(0, t_audio)
    #plt.show()
    self.canvas.draw()

  def select_filter(self):
    text = self.clicked.get()
    if text == "Reduce Background Noise":
      self.filter_background_noise()
    if text == "Equalization":
      self.equalization()
    if text == "Reverb":
      self.add_reverb()

  def filter_background_noise(self):
    use_file = self.get_effect_file()
    print(use_file)
    with AudioFile(use_file) as f:
      audio = f.read(f.frames)
    reduce_audio = nr.reduce_noise(y = audio, sr = RATE, stationary = True, prop_decrease=0.75)

    pedalboard = Pedalboard()
    pedalboard.append(Compressor(threshold_db=-20, ratio=2))
    pedalboard.append(NoiseGate(threshold_db=-50))

    effect_audio = pedalboard(reduce_audio, RATE)
    
    with AudioFile(f'{use_file.split(".wav")[0]}-filter.wav', 'w', RATE, effect_audio.shape[0]) as f:
      f.write(effect_audio)
  
  def equalization(self):
    use_file = self.get_effect_file()
    with AudioFile(use_file) as f:
      audio = f.read(f.frames)
    
    pedalboard = Pedalboard()
    pedalboard.append(LowShelfFilter())
    pedalboard.append(HighShelfFilter())
    pedalboard.append(PeakFilter())
    
    output_audio = pedalboard(audio, RATE)

    with AudioFile(f'{use_file.split(".wav")[0]}-eq.wav', 'w', RATE, output_audio.shape[0]) as f:
      f.write(output_audio)  

  def add_reverb(self):
    use_file = self.get_effect_file()
    with AudioFile(use_file) as f:
      audio = f.read(f.frames)
    pedalboard = Pedalboard()
    pedalboard.append(Reverb(room_size=0.75, wet_level=0.5))
    output_audio = pedalboard(audio, RATE)
    with AudioFile(f'{use_file.split(".wav")[0]}-reverb.wav', 'w', RATE, output_audio.shape[0]) as f:
      f.write(output_audio)

  def get_effect_file(self):
    use_file = self.input_effect_file.get("1.0", 'end-1c')
    if use_file == '':
      use_file = self.recent_recording
    use_file = use_file.strip()
    return use_file
  
  def quit(self):
    self.root.quit()

RecordingGUI()
