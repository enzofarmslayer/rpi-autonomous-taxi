# pip install tkinterweb==0.0.4 (valfritt)  # Tkinter ingår i vanliga Python på Windows
# Kör: python win_client_gui.py 192.168.1.42 5000

import socket, threading, sys, tkinter as tk
from tkinter import ttk

PI_IP = sys.argv[1] if len(sys.argv)>1 else "192.168.1.42"
PORT  = int(sys.argv[2]) if len(sys.argv)>2 else 5000

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
s.connect((PI_IP, PORT))

root = tk.Tk()
root.title("RC GUI (TCP)")

status = tk.StringVar(value="Connected to %s:%d" % (PI_IP, PORT))
tele_v = tk.StringVar(value="V=--.-V  v=--.-  seq=--")
ttk.Label(root, textvariable=status).pack(anchor="w", padx=10, pady=6)
ttk.Label(root, textvariable=tele_v, font=("Consolas",12)).pack(anchor="w", padx=10)

frm = ttk.Frame(root); frm.pack(padx=10, pady=10)
def send(cmd: str):
    try: s.sendall((cmd+"\n").encode("utf-8"))
    except OSError: status.set("Disconnected")

def on_up(_=None):    send("forward 120 1")
def on_down(_=None):  send("forward 80 1")   # bakåt när du implementerat typ i Pi/AVR
def on_left(_=None):  send("left 20 1")
def on_right(_=None): send("left -20 1")
def on_space(_=None): send("stop")

ttk.Button(frm, text="↑ Framåt", width=14, command=on_up).grid(row=0, column=1, padx=5, pady=5)
ttk.Button(frm, text="← Vänster", width=14, command=on_left).grid(row=1, column=0, padx=5, pady=5)
ttk.Button(frm, text="Stopp", width=14, command=on_space).grid(row=1, column=1, padx=5, pady=5)
ttk.Button(frm, text="Höger →", width=14, command=on_right).grid(row=1, column=2, padx=5, pady=5)
ttk.Button(frm, text="↓ Bakåt", width=14, command=on_down).grid(row=2, column=1, padx=5, pady=5)

# Piltangenter & Space
root.bind("<Up>", on_up)
root.bind("<Left>", on_left)
root.bind("<Right>", on_right)
root.bind("<Down>", on_down)
root.bind("<space>", on_space)

def rx_telemetry():
    buf = b""
    while True:
        try:
            data = s.recv(1024)
            if not data: break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                txt = line.decode("utf-8", "ignore")
                # Minimal parsing utan json: plocka ut siffror grovt
                # (Byt gärna till json.loads för robusthet.)
                # Ex: {"seq":12,"batt_v":7.62,"speed":3.20,"t":123.456}
                try:
                    parts = txt.replace("{","").replace("}","").split(",")
                    kv = dict(p.split(":") for p in parts)
                    seq = int(float(kv.get('"seq"', kv.get('seq','-1'))))
                    v   = float(kv.get('"batt_v"', kv.get('batt_v','0')))
                    sp  = float(kv.get('"speed"', kv.get('speed','0')))
                    tele_v.set(f"V={v:.2f}V  v={sp:.2f}  seq={seq}")
                except Exception:
                    tele_v.set(txt[:60])
        except OSError:
            break

threading.Thread(target=rx_telemetry, daemon=True).start()

def on_close():
    try: s.sendall(b"quit\n"); s.close()
    except: pass
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()
