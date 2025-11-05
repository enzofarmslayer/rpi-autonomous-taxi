# pip install tkinterweb==0.0.4 (valfritt)  # Tkinter ingår i vanliga Python på Windows
# Kör: python win_client_gui.py 192.168.1.42 5000

import socket, threading, sys, tkinter as tk 
from tkinter import ttk  #tkinter python gui bibliotek, ttk = themed tkinter

PI_IP = sys.argv[1] if len(sys.argv)>1 else "192.168.1.42" #Hämta ip  från kommandoraden.
PORT  = int(sys.argv[2]) if len(sys.argv)>2 else 5000   #Hämta port från kommandoraden

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  #skapa tcp anslutning. sockstream = tcp (sock_dgram = udp)
#af inet = address family: inteernet dvs ipv4  internet protokollet.
s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) #nodelay tar bort nagles algoritm (inte vänta på småskit att skickas samtidigt.)
s.connect((PI_IP, PORT)) #koppla till raspberryns ip och port

root = tk.Tk() #skapa fönstret
root.title("Max Verstappen controller (TCP)")

#Gui info 
status = tk.StringVar(value="Connected to %s:%d" % (PI_IP, PORT)) 
tele_v = tk.StringVar(value="V=--.-V  v=--.-  seq=--") #telemetridata
ttk.Label(root, textvariable=status).pack(anchor="w", padx=10, pady=6) # font och storlekt mm
ttk.Label(root, textvariable=tele_v, font=("Consolas",12)).pack(anchor="w", padx=10) #-||-

frm = ttk.Frame(root); frm.pack(padx=10, pady=10) #gui ruta, sstorlekt 10,10
def send(cmd: str): #hjälpfunktion varje gång vi skickar till pi:n. 
    try: s.sendall((cmd+"\n").encode("utf-8")) #\n ger radbrytning .encode utf 8 omvandlar texten till bytes. sendall skickar hela meddelandent över tcp socketen s.
    except OSError: status.set("Disconnected") #Vid error sätt status till disconnected.


#kallar på hjälpfunktionen send . =None innebär att argument kan komma men ignoreras.
def on_up(_=None):    send("fram") #skickar textsträngen till raspberry omvandlat till bytes mha send.
def on_down(_=None):  send("bak")  
def on_left(_=None):  send("vänster")
def on_right(_=None): send("höger")
def on_space(_=None): send("stop")

#fixar gui knapparna i frame, kopplas till kommandon mha command= . 
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


#hämtar data och visar den i gui 
def rx_telemetry():
    buf = b""
    while True:
        try:
            data = s.recv(1024) #läser in max 1024 bytes från tcp socket s.
            if not data: break #om ingen data bryt loopen och kalla oserror.
            buf += data
            while b"\n" in buf: #när radslut har kommit, dvs ett helt meddelande finns
                line, buf = buf.split(b"\n", 1) #splitta efter radbrytning
                txt = line.decode("utf-8", "ignore") #omvandla tillbaka från bytes till sträng 
                # Minimal parsing utan json: plocka ut siffror grovt
                # (Byt gärna till json.loads för robusthet.)
                # Ex: {"seq":12,"batt_v":7.62,"speed":3.20,"t":123.456}
                try:
                    parts = txt.replace("{","").replace("}","").split(",") #splittar med kommatecken och ersätter måsvingar för lättare läsning.
                    kv = dict(p.split(":") for p in parts) #delar upp innehållet till dict
                    seq = int(float(kv.get('"seq"', kv.get('seq','-1'))))
                    v   = float(kv.get('"batt_v"', kv.get('batt_v','0'))) #olika parametrar
                    sp  = float(kv.get('"speed"', kv.get('speed','0')))
                    tele_v.set(f"V={v:.2f}V  v={sp:.2f}  seq={seq}")
                except Exception:
                    tele_v.set(txt[:60])
        except OSError:
            break

threading.Thread(target=rx_telemetry, daemon=True).start() #bakgrundstråd för telemetrin daemon anger att det är en bakgrundstråd. 
#start startar bakgrundstråden direkt.

def on_close(): #logik för att stänga GUI
    try: s.sendall(b"quit\n"); s.close()
    except: pass
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop() #startar mainloopen
