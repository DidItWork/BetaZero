# SigmaZero
An implementation of Reinforcement Learning in game-playing according to Alpha Zero

## Logic

### Game Tree Node Attributes
- $N_i$, number of times node has been selected / number of times the node has been through the simulation (integer)
- $W_i$, the sum of expected value of the node (not an integer, "the number of wins for the node")
- $p$, policy values of child nodes
- $s$, representation of board state (8x8xN tensor)

### Alpha Zero MCTS
1. Selection: Start from root node (current game state) and select successive nodes based on Upper Confidence Bound Criterion (UCB) until a leaf node L is reached (a leaf node is any node that has a potential child from which no simulation has yet been initiated) or a terminal node.
$$\text{UCB} = \frac{W_i}{N_i}+p_ic\frac{\sqrt{N_i}}{1+n_i}$$
, where $c$ is a constant, $p_i$ is the policy of the child node and $n_i$ is its simulation count
3. Expansion: Unless L ends the game decisively for either player, randomly initialize an unexplored child node.
4. Backpropagation: Using the value generated by the neural network $f_\theta$, update the N and W values of the current node and all its parent nodes.
5. Repeat steps 1 to 3 for N iterations

### Self-Play and Training
1. Self-Play until the game ends using MCTS and $f_\theta$
2. Store the chosen action taken at each state and the values of the node (-1,0,1) depending on the player and whether he won or lost the game. One training sample should contain: (board state s, the action chosen $\pi$, the value of the node z)
3. Minimize loss function of the training samples in the batch.
$$l = (z-v)^2-\pi^T\log{p}+c||\theta||^2$$, $c$ is a constant

### Board State Representation

For the player's perspectives, this is what the tensor will look like. The board will change according to the current player.

White's View:

![white_view](https://github.com/DidItWork/Sigma-Zero/assets/63920704/39db00c8-c4b2-4578-b308-c185e408f54c)

Black's View:

![black_view](https://github.com/DidItWork/Sigma-Zero/assets/63920704/36f20d8a-d3e8-4731-8c5d-f24864e4eef9)

The board is represented as a (119, 8, 8) tensor, as calculated with MT + L. Where M = 14, T = 8, L = 7.

M represents the number of pieces/planes that are recorded in the board state. In our implementation, we mimicked AlphaZero's implementation of keeping track of all 12 pieces with 2 repetition planes. The order of the planes are as follows:
1. White Pawns
2. White Knights
3. White Bishops
4. White Rooks
5. White Queens
6. White King
7. Planes 7 to 12 are the same as 1 to 6, but for black pieces.
13. 1-fold repetition plane, a constant binary value
14. 2-fold repetition plane

T represents the number of half-steps that are kept track of. In this case we keep track of 8 half-steps, or 4 full turns. The latest update of the half-step is recorded in the first planes.

L is not time-tracked. It is a constant 7 planes that represents special cases of the board regardless of time. The order is as follows:
1. Current player's color
2. Total Moves that have been played to understand depth
3. White King's castling rights
4. White Queen's castling rights
5. Black King's castling rights
6. Black Queen's castling rights
7. No progress plane, for 50-move rule


### Action Representation

The actions are represented with an 8x8x73 tensor which can be flattened into a 4672 vector. The planes of the tensor represent the location on the board from which the chess piece should be picked up from.

- The first 8x7 channels/planes represent the number of squares to move (1 to 7) for the queen/rook/pawn/bishop/king as well as the direction. (Movement of pawn from 7th rank is assumed to be a promotion to queen)
- The next 8 channels/planes represent the direction to move the knight
- The last 9 channels represent the underpromotion of the pawn to knight, bishop, and rook resp. (through moving one step from the 7th rank or a diagonal capture from the 7th rank).
