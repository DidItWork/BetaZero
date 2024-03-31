import chess
import torch
import numpy as np
from typing import List, Union, Tuple


"""
MT + L

M = 6 + 6 + 2
6 pieces of each color
2 planes of repetition
    1 for 1 repetition within T moves
    1 for 2 repetitions within T moves
    The whole plane should be shown as 1 if the repetition happens
    
T = 8

L = 7
    1 for colour
    1 for Total move count
    1 for P1 castling
    1 for P2 castling
    1 for no-progress count
"""

class ChessTensor():
    def __init__(self, chess960=False):
        self.M = 14
        self.T = 8
        self.L = 7
        if chess960:
            self.__start_board(chess960=True)
        else:
            self.__start_board()

    # This is to get a single tensor representation of the board
    def __board_to_tensor(self, board) -> torch.Tensor:
        order = {
            chess.PAWN: 0,
            chess.KNIGHT: 1,
            chess.BISHOP: 2,
            chess.ROOK: 3,
            chess.QUEEN: 4,
            chess.KING: 5,
        }

        # 6 white + 6 black
        representation = torch.zeros(12, 8, 8)   

        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                # Determine the value to assign (positive for white, negative for black)
                channel = order[piece.piece_type]
                if piece.color == chess.BLACK:
                    channel += 6

                row, col = divmod(square, 8)
                representation[channel, row, col] = 1

        return representation

    def __start_board(self, chess960=False):
        self.board = chess.Board(chess960=chess960)

        # Get board current state
        board_tensor = self.__board_to_tensor(self.board)
        repetition_tensor = torch.zeros(2, 8, 8)
        current_representation = torch.cat([board_tensor, repetition_tensor], 0)

        # Adding L channel
        color = torch.zeros(1, 8, 8)
        total_moves = torch.zeros(1, 8, 8)
        white_king_castling = torch.ones(1, 8, 8)
        white_queen_castling = torch.ones(1, 8, 8)
        black_king_castling = torch.ones(1, 8, 8)
        black_queen_castling = torch.ones(1, 8, 8)
        no_progress = torch.zeros(1, 8, 8)
        L_tensor = torch.cat([color, total_moves, white_king_castling, white_queen_castling, black_king_castling, black_queen_castling, no_progress], 0)

        self.representation = torch.cat([current_representation, torch.zeros(self.M * (self.T - 1), 8, 8), L_tensor], 0)
    
    def move_piece(self, move: chess.Move) -> torch.Tensor:
        # Moving the board forward
        self.board.push(move)

        # Get board current state
        board_tensor = self.__board_to_tensor(self.board)

        # Add repetition tensor
        repetition_1 = False
        repetition_2 = False
        for i in range(0, 112, 14):
            repetition_1 = torch.all(board_tensor == self.representation[i: i + 12]) or repetition_1
            repetition_2 = (torch.all(board_tensor == self.representation[i: i + 12]) or repetition_2) and repetition_1

        repetition_1_tensor = torch.ones(1, 8, 8) if repetition_1 else torch.zeros(1, 8, 8)
        repetition_2_tensor = torch.ones(1, 8, 8) if repetition_2 else torch.zeros(1, 8, 8)

        # Get current tensor
        current_tensor = torch.cat([board_tensor, repetition_1_tensor, repetition_2_tensor], 0)
        
        # Adding L channel
        color = torch.zeros(1, 8, 8) if self.board.turn else torch.ones(1, 8, 8) # 0 means white, 1 means black
        total_moves = torch.Tensor([len(self.board.move_stack)]).reshape(1, 1, 1).expand(1, 8, 8)
        white_king_castling = torch.ones(1, 8, 8) if self.board.has_kingside_castling_rights(chess.WHITE) else torch.zeros(1, 8, 8)
        white_queen_castling = torch.ones(1, 8, 8) if self.board.has_queenside_castling_rights(chess.WHITE) else torch.zeros(1, 8, 8)
        black_king_castling = torch.ones(1, 8, 8) if self.board.has_kingside_castling_rights(chess.BLACK) else torch.zeros(1, 8, 8)
        black_queen_castling = torch.ones(1, 8, 8) if self.board.has_queenside_castling_rights(chess.BLACK) else torch.zeros(1, 8, 8)
        no_progress = torch.Tensor([self.board.halfmove_clock]).reshape(1, 1, 1).expand(1, 8, 8)

        L_tensor = torch.cat([color, total_moves, white_king_castling, white_queen_castling, black_king_castling, black_queen_castling, no_progress], 0)

        # Remove last M channels and L tensor
        self.representation = self.representation[:-self.M - self.L]

        # Combining all tensors
        self.representation = torch.cat([current_tensor, self.representation, L_tensor], 0)

    def undo_move(self) -> torch.Tensor:
        self.board.pop()

        # Remove first M channels
        self.representation = self.representation[self.M:]

        # Regenerate lost tensor
        old_tensor = self.__get_past_board_tensor(self.board)

        # Regenerate old L tensor
        color = torch.zeros(1, 8, 8) if self.board.turn else torch.ones(1, 8, 8) # 0 means white, 1 means black
        total_moves = torch.Tensor([len(self.board.move_stack)]).reshape(1, 1, 1).expand(1, 8, 8)
        white_king_castling = torch.ones(1, 8, 8) if self.board.has_kingside_castling_rights(chess.WHITE) else torch.zeros(1, 8, 8)
        white_queen_castling = torch.ones(1, 8, 8) if self.board.has_queenside_castling_rights(chess.WHITE) else torch.zeros(1, 8, 8)
        black_king_castling = torch.ones(1, 8, 8) if self.board.has_kingside_castling_rights(chess.BLACK) else torch.zeros(1, 8, 8)
        black_queen_castling = torch.ones(1, 8, 8) if self.board.has_queenside_castling_rights(chess.BLACK) else torch.zeros(1, 8, 8)
        no_progress = torch.Tensor([self.board.halfmove_clock]).reshape(1, 1, 1).expand(1, 8, 8)

        L_tensor = torch.cat([color, total_moves, white_king_castling, white_queen_castling, black_king_castling, black_queen_castling, no_progress], 0)

        # Remove last L channels
        self.representation = self.representation[:-self.L]

        # Add representation at the back
        self.representation = torch.cat([self.representation, old_tensor, L_tensor], 0)
        
    # Function to temporarily get the board state N moves ago, then restore the current state
    def __get_past_board_tensor(self, board) -> torch.Tensor:
        # Make sure n does not exceed the current move count
        n = self.T - 1
        n = min(n, len(board.move_stack))
        
        # Create a copy of the board for manipulation
        temp_board = board.copy()
        
        # Pop N moves to get the board state N moves ago
        for _ in range(n):
            temp_board.pop()

        temp_tensor = self.__board_to_tensor(temp_board)
        
        repetition1 = False
        repetition2 = False

        # Get repetition tensor
        n = min(self.T, len(temp_board.move_stack))
        for _ in range(n):
            temp_board.pop()
            old_tensor = self.__board_to_tensor(temp_board)

            if torch.all(old_tensor == temp_tensor):
                if repetition1:
                    repetition2 = True
                else:
                    repetition1 = True


        repetition_1_tensor = torch.ones(1, 8, 8) if repetition1 else torch.zeros(1, 8, 8)
        repetition_2_tensor = torch.ones(1, 8, 8) if repetition2 else torch.zeros(1, 8, 8)

        return torch.cat([temp_tensor, repetition_1_tensor, repetition_2_tensor], 0)

        
    def get_representation(self) -> torch.Tensor:
        # For white representation
        if self.board.turn:
            return torch.flip(self.representation, [1])
        else:
            # Changing order of representation
            copy = self.representation.clone()

            # Swapping order of representation for P1
            for i in range(self.T):
                start_channel = i * self.M
                end_channel = start_channel + 6

                copy[start_channel: end_channel, :, :], copy[start_channel + 6: start_channel + 12, :, :] = copy[start_channel + 6: start_channel + 12, :, :].clone(), copy[start_channel: end_channel, :, :].clone()
                
            # Swapping order of representation for L
            copy[-5:-4, :, :], copy[-3:-2, :, :] = copy[-3:-2, :, :].clone(), copy[-5:-4, :, :].clone()

            # Flipping the board for black
            return torch.flip(copy, [2])
        
    def get_moves(self) -> List[chess.Move]:
        return list(self.board.legal_moves)
    

    # New functions for mcts. State is of type board.
    def get_initial_state(self):
        return self.board
    
    def get_next_state(self, state, action, player=None):
        state.push(action)
        return state
    
    def get_valid_moves(self ,state):
        # print("get valid moves", state)
        return list(state.legal_moves)
    
    # def check_win(self, state):
    #     if action == None:
    #         return False
        
    #     state.push(action)

    #     if state.is_checkmate():
    #         state.pop()
    #         return True
    #     else:
    #         state.pop()
    #         return False

    def get_value_and_terminated(self, state, color=chess.WHITE):
        if state.is_game_over():
            winner = state.outcome().winner()
            if winner == None:
                #Draw
                return 0, True
            elif winner == color:
                return 1, True
            else:
                return -1, True

        return 0, False
    
    def get_opponent(self, player):
        return -player

    def get_opponent_value(self, value):
        return -value
    
    def change_perspective(self, state, player):
        return state * player

    def get_encoded_state(self, state):  # Something like get_rep, might delete function
        encoded_state = np.stack(
            (state == -1, state == 0, state == 1)
        ).astype(np.float32)

        return encoded_state
    
    
def validActionsToTensor(valid_moves:List[chess.Move], color=chess.WHITE) -> torch.tensor:
    """
    Returns a vector mask of valid actions
    """

    #Initialize empty action tensor
    actionTensor = torch.zeros(73*8*8)

    for valid_move in valid_moves:
        # print(valid_move)
        # print(actionToTensor(valid_move).nonzero())
        # print(tensorToAction(actionToTensor(valid_move)))
        actionTensor += actionToTensor(valid_move, color)
    
    return actionTensor
    

def actionToTensor(move:chess.Move, color:chess.Color=chess.WHITE) -> torch.tensor:

    moveTensor = torch.zeros(8*8*73)

    dir = {
        (0,-1) : 0,
        (1,-1) : 1,
        (1,0) : 2,
        (1,1) : 3,
        (0,1) : 4,
        (-1,1) : 5,
        (-1,0) : 6,
        (-1,-1) : 7,
    }

    knight_moves = {
        (1,-2) : 0, #0
        (2,-1) : 1, #1
        (2,1) : 2, #2
        (1,2) : 3, #3
        (-1,2) : 4, #4
        (-2,1) : 5, #5
        (-2,-1) : 6, #6
        (-1,-2) : 7, #7
    }

    def check_polarity(val) -> int:

        if val>0:
            return 1
        elif val<0:
            return -1
        else:
            return 0

    from_square = move.from_square
    to_square = move.to_square

    if color==chess.WHITE:
        row = 7-from_square//8
        col = from_square%8
        toRow = 7-to_square//8
        toCol = to_square%8
    else:
        row = from_square//8
        col = 7-from_square%8
        toRow = to_square//8
        toCol = 7-to_square%8
    
    # print(move, row, toRow, col, toCol)
    
    #Queen Move
    if toCol == col or toRow == row or abs(toRow-row)/abs(toCol-col)==1:

        #Check for underpromotion
        if move.uci()[-1] in "nbr":

            i = "nbr".index(move.uci()[-1])

            i*=3

            if toCol>col:

                #Right Diagonal Capture
                i+=1
                
            
            elif toCol<col:

                #Right Diagonal Capture
                i+=2
            

            moveTensor[(64+i)*8*8+row*8+col] = 1

        else:

            squares = max(abs(toRow-row), abs(toCol-col))

            direction = (check_polarity(toCol-col), check_polarity(toRow-row))

            # print(squares, direction)

            moveTensor[(dir[direction]*7+(squares-1))*64+row*8+col] = 1

    else:

        #Knight Move

        moveTensor[(56+knight_moves[toCol-col,toRow-row])*64+row*8+col] = 1
    
    return moveTensor


def tensorToAction(moves:torch.tensor, color:chess.Color=chess.WHITE) -> List[chess.Move]:

    #return all moves from tensor

    moves = moves.nonzero()

    chess_moves = []

    # move = int(torch.argmax(moves).item())

    lettering = "abcdefgh"
    numbering = [1,2,3,4,5,6,7,8]

    if color==chess.WHITE:
        numbering = numbering[::-1]
    else:
        lettering = lettering[::-1]

    #list for for movement, (x (+ ->), y (- ^))
    #direction for both sets of movements start from top and rotates clockwise
        
    dir = [
        (0,-1), #0
        (1,-1), #1
        (1,0), #2
        (1,1), #3
        (0,1), #4
        (-1,1), #5
        (-1,0), #6
        (-1,-1) #7
    ]

    knight_moves = [
        (1,-2), #0
        (2,-1), #1
        (2,1), #2
        (1,2), #3
        (-1,2), #4
        (-2,1), #5
        (-2,-1), #6
        (-1,-2) #7
    ]

    for move in moves:

        # print(move)

        #check plane of move
        plane = move//64

        #check position of move
        move %= 64
        row = move//8
        col = move%8

        promotion = ""

        if plane<56:
            #queen move
            direction = plane//7
            squares = 1+plane%7

            toCol = col+dir[direction][0]*squares
            toRow = row+dir[direction][1]*squares

            # if toRow == 7 and board.piece_at(chess.Square(row*8+col)) in "pP":
            #     promotion = "q"
        
        elif plane<64:
            #knight move
            direction = plane - 56
            
            toCol = col+knight_moves[direction][0]
            toRow = row+knight_moves[direction][1]

        else:

            plane -= 64

            #Pawn promotion if not pawn

            #Forward from row 7
            toRow = row-1

            if plane%3==1:

                #Capture from row 7 right diagonal
                toCol = col+1
            
            elif plane%3==2:

                #Capture from row 7 left diagonal
                toCol = col-1
            
            else:
                toCol = col

            promotion = "nbr"[plane//3]

        # print(row, toRow, col, toCol)

        move_str = f"{lettering[col]}{numbering[row]}{lettering[toCol]}{numbering[toRow]}{promotion}"

        chess_moves.append(chess.Move.from_uci(move_str))

    return chess_moves


# chesser = ChessTensor(chess960=True)

# for i in range(12):
#     moves = chesser.get_moves()
#     chesser.move_piece(moves[0])

# rep1 = chesser.get_representation()

# moves = chesser.get_moves()
# chesser.move_piece(moves[0])
# chesser.undo_move()

# rep2 = chesser.get_representation()

# # 14, 28, 42, 56, 70, 84, 98, 112
# # 0 , 14, 28, 42, 56, 70, 84, 98


# for i in range(119):
#     if not torch.all(rep1[i] == rep2[i]):
#         print("expected", rep1[i])
#         print("got", rep2[i])



# if __name__=="__main__":

    # pass

    # #for testing

    # move = torch.zeros(8*8*73)

    # board = chess.Board()

    # move[8*8*72] = 1

    # print(tensorToAction(move))

    # game = ChessTensor()
    # game.move_piece(chess.Move.from_uci("e2e4"))
    # game.move_piece(chess.Move.from_uci("d7d6"))
    # board = game.get_representation()
    # print("white\n",board[0])
    # print(board[14])
    # print("black\n",board[6])
    # print(board[20])

    # move = chess.Move.from_uci("a1e5")
    # print(tensorToAction(actionToTensor(move)))
