// g++ -O2 -std=c++17 -pthread -o pi_comm pi_comm.cpp
// Kör: ./pi_comm 0.0.0.0 5000
// Gör två trådar: (1) tar emot kommandorader från PC, (2) skickar telemetri (JSON per rad).
// TODO senare: mappa kommandon -> skriv [0xAA,TYP,LEN,DATA...] till UART.

#include <arpa/inet.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <unistd.h>
#include <atomic>
#include <chrono>
#include <cstring>
#include <iostream>
#include <mutex>
#include <string>
#include <thread>

// --- NEW: UART includes
#include <fcntl.h>
#include <termios.h>

// --- NEW: tiny UART helper
static int open_uart(const char* dev, int baud){
    int fd = ::open(dev, O_RDWR | O_NOCTTY | O_NONBLOCK);
    if(fd < 0){ perror("open_uart"); return -1; }

    termios tio{};
    if(tcgetattr(fd, &tio) < 0){ perror("tcgetattr"); ::close(fd); return -1; }

    cfmakeraw(&tio);
    tio.c_cflag |= (CLOCAL | CREAD);
    // 8N1
    tio.c_cflag &= ~PARENB;
    tio.c_cflag &= ~CSTOPB;
    tio.c_cflag &= ~CSIZE;
    tio.c_cflag |= CS8;
    // Baud
    speed_t spd = B115200;
    switch(baud){
        case 9600: spd=B9600; break;
        case 19200: spd=B19200; break;
        case 38400: spd=B38400; break;
        case 57600: spd=B57600; break;
        case 115200: default: spd=B115200; break;
    }
    cfsetispeed(&tio, spd);
    cfsetospeed(&tio, spd);

    // Apply and make blocking reads/writes (clear O_NONBLOCK after config)
    if(tcsetattr(fd, TCSANOW, &tio) < 0){ perror("tcsetattr"); ::close(fd); return -1; }
    int flags = fcntl(fd, F_GETFL);
    fcntl(fd, F_SETFL, flags & ~O_NONBLOCK);
    tcflush(fd, TCIOFLUSH);
    return fd;
}

static void set_nodelay(int fd){
    int one=1; setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &one, sizeof(one));
}

int main(int argc, char**argv){
    const char* host = (argc>1)? argv[1] : "0.0.0.0";
    int port = (argc>2)? std::stoi(argv[2]) : 5000;
    
    const char* uart_dev = (argc>3)? argv[3] : "/dev/ttyUSB0";
    int uart_baud = (argc>4)? std::stoi(argv[4]) : 115200;

    // --- NEW: open UART once at startup
    int uart_fd = open_uart(uart_dev, uart_baud);
    if(uart_fd < 0){
        std::cerr << "VARNING: Kunde inte öppna UART ("<<uart_dev<<"). Fortsätter utan.\n";
    } else {
        std::cout << "UART öppen på " << uart_dev << " @ " << uart_baud << " baud\n";
    }
    
    int srv = ::socket(AF_INET, SOCK_STREAM, 0); //skapa tcp anslutning. sockstream = tcp (sock_dgram = udp)
                                                //af inet = address family: inteernet dvs ipv4  internet protokollet.
                                                //vid misslyckande returvärde < 0
    if(srv<0){ perror("socket"); return 1; }
    int one=1; setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));

    sockaddr_in addr{}; addr.sin_family=AF_INET; addr.sin_port=htons(port); //ipv4 internet protokoll
    addr.sin_addr.s_addr = inet_addr(host);
    if(bind(srv, (sockaddr*)&addr, sizeof(addr))<0){ perror("bind"); return 1; } //Kopplar socket till lokal ip
    if(listen(srv, 1)<0){ perror("listen"); return 1; }
    std::cout<<"Lyssnar på "<<host<<":"<<port<<"\n";

    for(;;){ //oändlig loop
        sockaddr_in cli{}; socklen_t cl=sizeof(cli);
        int fd = accept(srv,(sockaddr*)&cli,&cl);
        if(fd<0){ perror("accept"); continue; }  //misslyckas accept hopppa över och fortsätt.
        set_nodelay(fd);
        std::cout<<"Klient ansluten\n";

        std::atomic<bool> stop{false};
        std::mutex send_mx;

        // RX: ta emot kommandon (text-rader), mappa senare till [AA TYP LEN DATA]
        std::thread t_rx([&](){
            std::string buf;
            char tmp[1024];
            while(!stop){
                ssize_t r = recv(fd, tmp, sizeof(tmp), 0);
                if(r<=0) break;
                buf.append(tmp, tmp+r);
                size_t pos;
                while((pos = buf.find('\n')) != std::string::npos){
                    std::string line = buf.substr(0,pos); buf.erase(0,pos+1);
                    if(line=="quit") { stop=true; break; }
                    // Här: Mappa line t.ex. "forward 120 1", "left 20 1", "stop"
                    std::cout<<"CMD: "<<line<<"\n";
                    // --- NEW: map "fram" (Up arrow from Win GUI) -> send single byte 0x01 over UART
                    if(uart_fd >= 0 && line=="fram"){
                        uint8_t b = 0x01;
                        ssize_t wr = ::write(uart_fd, &b, 1);
                        if(wr == 1) {
                            std::cout << "Sent 1 byte (0x01) to UART\n";
                        } else {
                             perror("UART write");
                        }
                        // (Optional) flush to push it immediately
                        tcdrain(uart_fd);
                    }

                    // TODO: skriv UART-ram: [0xAA, typ, len, data...]  (enligt spec). :contentReference[oaicite:3]{index=3}
                }
            }
            stop=true;
        });

        // TX: skicka telemetri 20 Hz (JSON per rad)
        std::thread t_tx([&](){
            int seq=0;
            using namespace std::chrono;
            while(!stop){
                double batt = 7.6 + 0.05*(seq%10);
                double speed= 0.4*(seq%15);
                auto  now  = duration<double>(steady_clock::now().time_since_epoch()).count();
                char line[256];
                int n = snprintf(line, sizeof(line),
                    "{\"seq\":%d,\"batt_v\":%.2f,\"speed\":%.2f,\"t\":%.3f}\n",
                    seq++, batt, speed, now);
                std::lock_guard<std::mutex> lk(send_mx);
                if(send(fd, line, n, 0)<=0){ stop=true; break; }
                std::this_thread::sleep_for(std::chrono::milliseconds(50)); // 20 Hz
            }
        });

        t_rx.join(); t_tx.join();
        close(fd);
        std::cout<<"Klient frånkopplad\n";
    }
    // --- NEW: close UART on exit
    if(uart_fd >= 0) ::close(uart_fd);
    return 0;
}
