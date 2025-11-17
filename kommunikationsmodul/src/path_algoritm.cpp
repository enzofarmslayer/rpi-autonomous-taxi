#include <iostream>
#include <utility>
#include <vector>
#include <map>
#include <string>
#include <queue>
#include <algorithm>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <cstring>


using namespace std;
using Edge = pair<int, int>;
using Graph = vector<vector<Edge>>;

bool can_drive(const string& from, const string& to, string& start, string& goal)
{
    cout << "From: " << from << " To: " << to << endl;
    if (from == start && to == "5") {
        return false;
    } else if ((from == "2" || from == "4") && to == goal) {
        return false;
    }
    return true;
}

vector<string> path(string s, string t) {
    map<string, vector<string>> row_net = {
        {"1", {"2", "3"}},
        {"2", {"1", "4", "5"}},
        {"3", {"1", "4", "6"}},
        {"4", {"2", "3", "5", "6"}},
        {"5", {"2", "4", "7"}},
        {"6", {"4", "3", "7"}},
        {"7", {"5", "6"}}
    };

    string start = s;
    string target = t;
    map<string, vector<string>> ns_tb = {
        {"5", {"7"}},
        {"1", {"2"}},
        {"3", {"1"}},
        {"6", {"3", "4"}},
    };

    map<string, vector<string>> cl_tb = {
        {"5", {"7"}},
        {"1", {"2"}},
        {"3", {"4", "6"}},
        {"6", {"4", "3"}},
    };

    vector<string> not_start = ns_tb[start];
    vector<string> correct_last = cl_tb[target];

    vector<string> complete;

    queue<pair<string, vector<string>>> st;

    st.push({ start, {} });

    while (!st.empty()) {
        auto current = st.front();
        st.pop();

        string current_node = current.first;
        vector<string> visited_nodes = current.second;

        string previous = !visited_nodes.empty() ? visited_nodes.back() : "None";
        string pre_previous = visited_nodes.size() >= 2 ? visited_nodes[visited_nodes.size() - 2] : "None";
        
        if (current_node == target && !visited_nodes.empty()) {
            if ((find(correct_last.begin(), correct_last.end(), previous) != correct_last.end())) {
                visited_nodes.push_back(current_node);
                complete = visited_nodes;
                break;
            }
        }
        
        visited_nodes.push_back(current_node);

        for (const auto& neighbour : row_net[current_node]) {
            if ((find(not_start.begin(), not_start.end(), neighbour) != not_start.end()) && (visited_nodes.size() == 1)) {
                continue;
            }
            if (previous != neighbour && pre_previous != neighbour) {
                st.push({ neighbour, visited_nodes });
            }
        }
    }
    
    for (const auto& node : complete) {
        cout << "NODE: " << node << endl;
    }

    return complete;
}

string invert_turn(const string& t) {
    if (t == "H") return "V";
    if (t == "V") return "H";

    return t;
}

vector<string> path_to_turns(vector<string> path) {
    vector<string> turns;
    map<string, vector<pair<string, string>>> turn_table = {
        {"1", {{"2", "H"}, {"3", "V"}}},
        {"2", {{"1", "V"}, {"5", "F"}, {"4", "H"}}},
        {"3", {{"1", "H"}, {"4", "V"}, {"6", "F"}}},
        {"4", {{"2", "V"}, {"3", "H"}, {"5", "H"}, {"6", "V"}}},
        {"5", {{"2", "F"}, {"4", "V"}, {"7", "H"}}},
        {"6", {{"4", "H"}, {"3", "F"}, {"7", "V"}}},
        {"7", {{"6", "H"}, {"5", "V"}}}
    };
    string start = path.front();
    path.erase(path.begin());

    string current = start;
    for (const auto& node : path) {
        vector<pair<string, string>> pot_turns = turn_table[current];
        for (const auto& comp_node : pot_turns) {
            if (comp_node.first == node) {
                turns.push_back(comp_node.second);
                current = node;
            }
        }
    }

    return turns;
}

uint8_t encode_turn(const string& turn) {
    if (turn == "H") return 0b01;
    if (turn == "V") return 0b10;
    if (turn == "F") return 0b11;
    return 0b00; // Invalid
}

int init_drive_socket()
{
    int fd = ::socket(AF_UNIX, SOCK_DGRAM, 0);
    if (fd < 0) { perror("socket"); return -1; }

    // CLIENT-SOCKET (avsändarens egen)
    sockaddr_un addr{};
    addr.sun_family = AF_UNIX;
    std::strcpy(addr.sun_path, "/tmp/path_cmd_client.sock");

    ::unlink(addr.sun_path);

    if (::bind(fd, (sockaddr*)&addr, sizeof(addr)) < 0) {
        perror("bind client");
        ::close(fd);
        return -1;
    }

    return fd;
}


bool send_drive_cmd(int fd, uint8_t cmd)
{
    sockaddr_un addr{};
    addr.sun_family = AF_UNIX;
    std::strcpy(addr.sun_path, "/tmp/drive_cmd.sock");

    // Skicka kommando
    ssize_t n = sendto(fd, &cmd, 1, 0,
                       (sockaddr*)&addr, sizeof(addr));
    if (n != 1) {
        perror("sendto");
        return false;
    }

    // Vänta på DONE
    char ack;
    n = recv(fd, &ack, 1, 0);
    if (n == 1 && ack == 'D') return true;

    return false;
}


int main()
{
    vector<string> p = path("6", "3");
    vector<string> turns = path_to_turns(p);

    int fd = init_drive_socket();
    if (fd < 0) return 1;

    for (const auto& t : turns) {
        cout << "TURN: " << t << " -> encoded: " << (int)encode_turn(t) << endl;
        uint8_t cmd = encode_turn(t);

        bool ok = send_drive_cmd(fd, cmd);
        if (!ok) {
            cout << "Fel vid manöver" << endl;
            break;
        }
    }

    ::close(fd);
}

