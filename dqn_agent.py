import random
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from collections import deque
import requests

BASE_URL = "http://localhost:5000"
ROWS, COLS = 10, 10
N_ACTIONS = ROWS * COLS

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

class BattleshipEnv:
    def reset(self):
        requests.post(f"{BASE_URL}/game/new", json={"rows": ROWS, "cols": COLS})
        self.raw_board = np.full((ROWS, COLS), -1, dtype=np.float32)
        self.done = False
        self.shots = 0
        return self._state()

    def step(self, action):
        row, col = divmod(action, COLS)
        resp = requests.post(f"{BASE_URL}/game/shoot", json={"row": row, "col": col}).json()

        self.raw_board = np.array(resp["board"], dtype=np.float32)
        self.done = resp["won"]
        result = resp["result"]
        self.shots += 1

        # Reward: penalise misses hard, reward hits, reward sinking, big win bonus
        # Critically: win bonus is REDUCED by shots taken, so faster = better
        if result == 0:
            reward = -2.0
        elif result == 1:
            reward = 10.0
        else:           # ship sunk (result is ship id: 2,3,-3,4,5)
            reward = 30.0
        if self.done:
            reward += max(0, 200 - self.shots * 2)  # up to +200 for fast wins

        return self._state(), reward, self.done

    def _state(self):
        # Encode as 3 binary channels flattened:
        # channel 0: unshot cells (raw == -1)
        # channel 1: misses     (raw ==  0)
        # channel 2: hits/sunk  (raw not in {-1, 0})
        unshot = (self.raw_board == -1).astype(np.float32)
        miss   = (self.raw_board ==  0).astype(np.float32)
        hit    = (~np.isin(self.raw_board, [-1, 0])).astype(np.float32)
        return np.concatenate([unshot.flatten(), miss.flatten(), hit.flatten()])

    def valid_actions(self):
        return [i for i, v in enumerate(self.raw_board.flatten()) if v == -1.0]


# ---------------------------------------------------------------------------
# Network — takes 3*100=300 inputs (binary channels)
# ---------------------------------------------------------------------------

class DQN(nn.Module):
    def __init__(self, input_size=N_ACTIONS * 3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_size, 512),
            nn.ReLU(),
            nn.Linear(512, 512),
            nn.ReLU(),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Linear(256, N_ACTIONS),
        )

    def forward(self, x):
        return self.net(x)


# ---------------------------------------------------------------------------
# Replay buffer
# ---------------------------------------------------------------------------

class ReplayBuffer:
    def __init__(self, capacity=100_000):
        self.buf = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done):
        self.buf.append((state, action, reward, next_state, done))

    def sample(self, batch_size):
        batch = random.sample(self.buf, batch_size)
        s, a, r, s2, d = zip(*batch)
        return (
            torch.tensor(np.array(s),  dtype=torch.float32),
            torch.tensor(a,            dtype=torch.long),
            torch.tensor(r,            dtype=torch.float32),
            torch.tensor(np.array(s2), dtype=torch.float32),
            torch.tensor(d,            dtype=torch.float32),
        )

    def __len__(self):
        return len(self.buf)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class DQNAgent:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")

        self.policy_net = DQN().to(self.device)
        self.target_net = DQN().to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=5e-4)
        self.buffer    = ReplayBuffer()

        self.gamma         = 0.95   # lower gamma: prioritise immediate hits over far future
        self.batch_size    = 128
        self.target_update = 500
        self.train_start   = 1_000

        self.epsilon       = 1.0
        self.epsilon_min   = 0.05
        self.epsilon_decay = 0.997  # ~1000 episodes to reach minimum

        self.steps = 0

    def select_action(self, state, valid_actions):
        if not valid_actions:
            raise RuntimeError("No valid actions.")

        if random.random() < self.epsilon:
            return random.choice(valid_actions)

        state_t = torch.tensor(state, dtype=torch.float32).unsqueeze(0).to(self.device)
        with torch.no_grad():
            q = self.policy_net(state_t).squeeze(0).cpu().numpy()

        mask = np.full(N_ACTIONS, -np.inf)
        mask[valid_actions] = q[valid_actions]
        return int(np.argmax(mask))

    def train_step(self):
        if len(self.buffer) < self.train_start:
            return None

        s, a, r, s2, d = self.buffer.sample(self.batch_size)
        s, a, r, s2, d = (t.to(self.device) for t in (s, a, r, s2, d))

        q_pred = self.policy_net(s).gather(1, a.unsqueeze(1)).squeeze(1)

        with torch.no_grad():
            # Mask already-shot cells: unshot channel is s2[:, :N_ACTIONS]
            next_valid_mask = s2[:, :N_ACTIONS] > 0.5  # True where cell is unshot
            q_next_all = self.policy_net(s2)
            q_next_all_masked = q_next_all.masked_fill(~next_valid_mask, -float("inf"))
            next_a   = q_next_all_masked.argmax(1)
            q_next   = self.target_net(s2).gather(1, next_a.unsqueeze(1)).squeeze(1)
            q_target = r + self.gamma * q_next * (1 - d)

        loss = nn.SmoothL1Loss()(q_pred, q_target)
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.policy_net.parameters(), 10)
        self.optimizer.step()

        self.steps += 1
        if self.steps % self.target_update == 0:
            self.target_net.load_state_dict(self.policy_net.state_dict())

        return loss.item()

    def decay_epsilon(self):
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    def save(self, path="dqn_battleship.pth"):
        torch.save({
            "policy":  self.policy_net.state_dict(),
            "target":  self.target_net.state_dict(),
            "optim":   self.optimizer.state_dict(),
            "epsilon": self.epsilon,
            "steps":   self.steps,
        }, path)
        print(f"Checkpoint saved → {path}")

    def load(self, path="dqn_battleship.pth"):
        ckpt = torch.load(path, map_location=self.device)
        self.policy_net.load_state_dict(ckpt["policy"])
        self.target_net.load_state_dict(ckpt["target"])
        self.optimizer.load_state_dict(ckpt["optim"])
        self.epsilon = ckpt["epsilon"]
        self.steps   = ckpt["steps"]
        print(f"Checkpoint loaded ← {path}  (epsilon={self.epsilon:.3f}, steps={self.steps})")


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------

def train(n_episodes=15_000, print_every=100, save_every=500):
    env   = BattleshipEnv()
    agent = DQNAgent()

    shot_history = deque(maxlen=print_every)

    for ep in range(1, n_episodes + 1):
        state = env.reset()
        shots = 0

        while True:
            valid  = env.valid_actions()
            action = agent.select_action(state, valid)
            next_state, reward, done = env.step(action)
            agent.buffer.push(state, action, reward, next_state, done)
            agent.train_step()
            state = next_state
            shots += 1
            if done:
                break

        agent.decay_epsilon()
        shot_history.append(shots)

        if ep % print_every == 0:
            avg = np.mean(shot_history)
            print(f"Episode {ep:6d} | avg shots: {avg:.1f} | epsilon: {agent.epsilon:.3f} | buffer: {len(agent.buffer)}")

        if ep % save_every == 0:
            agent.save()

    agent.save()
    return agent


# ---------------------------------------------------------------------------
# Watch a trained agent play one game
# ---------------------------------------------------------------------------

def play_one_game(agent):
    env   = BattleshipEnv()
    state = env.reset()
    agent.epsilon = 0.0

    shots = 0
    while True:
        valid  = env.valid_actions()
        action = agent.select_action(state, valid)
        row, col = divmod(action, COLS)
        state, reward, done = env.step(action)
        shots += 1
        print(f"Shot {shots:3d}: ({row}, {col})  reward={reward:+.0f}")
        if done:
            print(f"\nGame over in {shots} shots.")
            break


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if "--play" in sys.argv:
        agent = DQNAgent()
        agent.load()
        play_one_game(agent)
    else:
        train()