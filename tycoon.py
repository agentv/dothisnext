#!/usr/bin/python

import os
import sys
import random
import pickle
import logging
from google.appengine.ext import db
from google.appengine.ext.webapp import template
from google.appengine.api import users

import brainbank

#######################################################
# some tycoon constants
game_length = 48
board_width = 8
board_length = 8

def newboard(nm,rows=board_length,cols=board_width):
   b = Board(cols,rows)
   b.playername = nm # this may have no function
   return b


# there's probably a construct that does this work of these
# next two functions, but I don't know it
def zero_bound (x):
   if x >= 0:
      return x
   else:
      return 0

def upper_bound (x,limit):
   if x > limit:
      return limit
   else:
      return x

def goto(player,board,tile,x,y):
   'moves player to a new tile and returns true on success'
   if (x < 0 or x >= board.colcount or
         y < 0 or y >= board.rowcount):
         return None
   test_tile = board.get_tile_bypos(x,y)
   if test_tile.add_player(player): 
      tile.remove_player()
      player.here_x = x
      player.here_y = y
      return test_tile
   return None

######################################################
class CommandProcessor(object): 
   'this class processes game commands'
   
# this is a known atrocity. When I have more fire in my belly, I"ll 
# convert this. It should have each direction be a little shim, and then
# a call into a move_finisher() method.  Even better would be a vector
# of lambda functions that call the finalizer appropriately
#
# update: I can convert this -- we can use a vector of lambda functions
# to calculate deltas for moving in a particular direction.
#
# the ideal though, is to retool CommandProcessor to run from 
# a working instance so we can cut out with the global functions
# and clunky structure

   def west(p,b,t):
      next_tile = t
      nx = p.here_x-1; ny = p.here_y 
      test_tile = goto(p,b,t,nx,ny) 
      if test_tile: 
         next_tile = test_tile
      return next_tile

   def north(p,b,t):
      next_tile = t
      nx = p.here_x; ny = p.here_y-1
      test_tile = goto(p,b,t,nx,ny)
      if test_tile: 
         next_tile = test_tile
      return next_tile

   def east(p,b,t):
      next_tile = t
      nx = p.here_x+1; ny = p.here_y
      test_tile = goto(p,b,t,nx,ny)
      if test_tile:
         next_tile = test_tile
      return next_tile

   def south(p,b,t):
      next_tile = t
      nx = p.here_x; ny = p.here_y+1
      test_tile = goto(p,b,t,nx,ny)
      if test_tile:
         next_tile = test_tile
      return next_tile

   def northeast(p,b,t):
      next_tile = t
      nx = p.here_x+1; ny = p.here_y-1
      test_tile = goto(p,b,t,nx,ny)
      if test_tile:
         next_tile = test_tile
      return next_tile

   def northwest(p,b,t):
      next_tile = t
      nx = p.here_x-1; ny = p.here_y-1
      test_tile = goto(p,b,t,nx,ny)
      if test_tile:
         next_tile = test_tile
      return next_tile
   def southwest(p,b,t):
      next_tile = t
      nx = p.here_x-1; ny = p.here_y+1
      test_tile = goto(p,b,t,nx,ny)
      if test_tile:
         next_tile = test_tile
      return next_tile

   """
   def southeast(p,b,t):
      nx = p.here_x+1; ny = p.here_y+1
      return CommandProcessor.move_execute(p,b,t,nx,ny)
   """
   def southeast(p,b,t):
      next_tile = t
      nx = p.here_x+1; ny = p.here_y+1
      test_tile = goto(p,b,t,nx,ny)
      if test_tile:
         next_tile = test_tile
      return next_tile

   def move_execute(p,b,t,nx,ny):
      next_tile = t
      test_tile = goto(p,b,t,nx,ny)
      if test_tile:
         next_tile = test_tile
      return next_tile

   direction_vector = {
      'north': north,
      'south': south,
      'west': west,
      'east': east,
      'northeast': northeast,
#      'southeast': lambda p: (p.here_x+1,p.here_y+1)
      'southeast': southeast,
      'northwest': northwest,
      'southwest': southwest,
   }

   def move(p,b):
      thistile = b.get_tile_bypos(p.here_x,p.here_y)
      dir = p.direction
      if dir:
         newtile = CommandProcessor.direction_vector[dir](p,b,thistile)
#         newtile = move_execute(p,b,thistile,direction_vector[dir])
         if newtile == thistile:
            return 'You are not going anywhere'
         else:
            return ''
      else:
         return 'You must indicate a legal move direction'

   def mine(p,b):
      # locate the current tile for this player`
      tile = b.get_tile_bypos(p.here_x,p.here_y)
      mineral_yield = 2 # game pref
      if tile.minerals > 0:
         mineral_yield = 2 # game pref
         if tile.minerals >= mineral_yield:
            tile.minerals -= mineral_yield
            p.minerals += mineral_yield
         else: 
            p.minerals += tile.minerals
            tile.minerals = 0 
         return 'Your industrious nature brings you success!'
      else:
         return 'You cannot mine an empty vein'
      
   def harvest(p,b):
      tile = b.get_tile_bypos(p.here_x,p.here_y)
      if tile.crops > 0:
         harvest_size = 3 # this should be game pref 
         if tile.crops >= harvest_size:
            tile.crops -= harvest_size
            p.crops += harvest_size
         else:
            p.crops += tile.crops
            tile.crops = 0 
         return 'Hard work brings you success!'
      else:
         return 'You cannot harvest an empty field'

   def cultivate(p,b):
      'allows player to increase available crops'
      tile = b.get_tile_bypos(p.here_x,p.here_y)
      roll = dice(100)
      roll += (p.farming_ability * 2)
      if roll > 55: # this should become a game preference
         p.farming_ability += 1
         tile.crops += 1
         return 'You have increased the yield in this plot'
      else:
         return 'Keep trying. Success is in sight'

   def build(p,b):
      'allows player to increase minerals available'
      tile = b.get_tile_bypos(p.here_x,p.here_y)
      roll = dice(100)
      roll += (p.mining_ability * 2)
      if roll > 70: # should become a game preference
         p.mining_ability += 1
         tile.minerals += 1
         return 'Hard work pays off. New minerals are available.'
      else:
         return 'Keep working. You can do this.'

   def clear_scores(p,b):
      'resets the leader board'
      q = ScoreLine.all()
      logging.info('clearing the scorebaord')
      for line in q:
         line.delete()
      return 'Player scoreboard reset'

   def clear_playerdb(p,b):
      'I do not know if this is a good idea'
      q = SaveablePlayer.all()
      logging.info('clearing the player DB')
      for p in q:
         p.delete()
      return 'Player database reset'

   cmd_vector = { 
      'harvest': harvest, 
      'mine': mine, 
      'clear_scores': clear_scores,
      'cultivate': cultivate, 
      'build': build, 
      'move': move, 
      'clear_playerdb': clear_playerdb, # let's get this fixed soon
   }

   def process_cmd(self,cmd,player,board):
      'returns a string given legal command, player and board instance'
      if self.cmd_vector.has_key(cmd):
         response = self.cmd_vector[cmd](player,board)
         board.clock += 1
# silly constants - turn this into game pref
         if board.clock > 48: # game_length
            return 'game over'
         if board.clock % 12 == 0: # length of a "year" - game pref
            board.yield_crops()
         return response
      else:
         return 'Please try a legal command'

# end of CommandProcessor
######################################################
class ScoreLine(db.Model):
   'Holds one player best score'
   name = db.StringProperty()
   total_worth = db.IntegerProperty()
   yield_ratio = db.FloatProperty()
######################################################
class SaveablePlayer(db.Model):
   'class holds a pickled instance of a Player object'
   stored_player = db.BlobProperty()
   name = db.StringProperty()

   def decant (self):
      'returns an instance of player or None if an exception occurs'
      try:
         newplayer = pickle.loads(self.stored_player)
      except pickle.PickleError:
         logging.error('Error unpickling the player instance')
         return None
      return newplayer

######################################################
class Player(object):
   'base class for a game player'
   def __init__(self, n, hx=2, hy=2, c=30, m=5):
      self.name = n
      self.crops = c
      self.minerals = m
      self.mining_ability = 5
      self.farming_ability = 5
      self.board = None # if we set this properly, we can reduce parm passing
      self.direction = '' # these next three registers are helpful for moving
      self.here_x = hx
      self.here_y = hy

   def preserve(self,splayer):
      try:
         splayer.stored_player = pickle.dumps(self)
      except pickle.PickleError:
         logging.error('Error pickling the player instance')
         return None
      return splayer

   def render(self,tmpl='playerpatch.html',theme=''):
#this formula needs to be extracted and delegated to a scoring routine
      self.worth = (self.crops * 2) + (self.minerals * 5)
      template_values = {
         'player': self,
      }
      path=os.path.join(os.path.dirname(__file__), tmpl)
      face = template.render(path,template_values)
      return face

# end of Player
######################################################
class Tile(object):
   'class for a gameboard tile'
# some static maximums for the Tile class
   mine_max = 4
   crop_max = 8

   def __init__(self, m=0, f=1, c=0):
      self.minerals = m
      self.fertility = f
      self.crops = c
      self.player_name = '' # a hack for displaying the player
      self.player = None 
      self.seed_me()

   def add_player(self, player):
      if self.player != None:
         return False
      else:
         self.player = player 
         self.player_name = 'XX'
         return True

   def remove_player (self):
      self.player = None
      self.player_name = ''

   """
   def web_render(self):
      crop_ctable = ('#FFFFCC', '#FFFF99', '#FFFF66', '#FFFF33')
      mine_ctable = ('#999900', '#996600', '#993300', '#990000') 
      fertility_ctable = ('#66FF99', '#66FF66', '#66FF33','#66FF00')

      cindex = upper_bound(self.crops/3, 3)
      crop_bg = crop_ctable[cindex]
      cindex = upper_bound(self.minerals/2, 3)
      mine_bg = mine_ctable[cindex]
      cindex = upper_bound(self.fertility/2, 3)
      fertility_bg = fertility_ctable[cindex]
      player_bg = '#CCCCCC'
      r = '<div align="center"><table class="gametile">'
      r += '<tr><td bgcolor="%s">M:%s</td>' \
         % (mine_bg, self.minerals)
      r += '<td bgcolor="%s"><b>%s</b></td></tr>' \
         % (player_bg, self.player_name)
      r += '<tr><td bgcolor="%s">F:%s</td>' \
         % (fertility_bg, self.fertility)
      r += '<td bgcolor="%s">C:%s</td></tr>' \
         % (crop_bg,self.crops)
      r += '</table></div>'
      return r
   """

   def render(self):
      crop_ctable = ('#FFFFCC', '#FFFF99', '#FFFF66', '#FFFF33')
      mine_ctable = ('#FFFFCC', '#DBB8A6', '#B8704C', '#993300') 
      fertility_ctable = ('#FFFFCC', '#A3FF85', '#85FF5C','#66FF33', '#52CC29')

      try: 
         cindex = zero_bound(upper_bound(self.crops/2, 3))
         crops_glow = crop_ctable[cindex] 
         cindex = zero_bound(upper_bound(self.minerals/2, 3))
         mineral_glow = mine_ctable[cindex] 
         cindex = zero_bound(upper_bound(self.fertility, 4))
         fertility_glow = fertility_ctable[cindex]
      except IndexError,e:
         logging.error('bad index ',e)
         crops_glow = mineral_glow = fertility_glow = ''

      if self.player:
         player_glow = '#CCCCCC'
      else:
         player_glow = ''

      template_values = {
         'player_piece': self.player_name,
         'player_glow': player_glow,
         'fertility_glow': fertility_glow,
         'fertility_count': self.fertility,
         'crops_glow': crops_glow,
         'crops_count': self.crops,
         'mineral_glow': mineral_glow,
         'mineral_count': self.minerals,
      }
      path=os.path.join(os.path.dirname(__file__), 'tilepatch.html')
      face = template.render(path,template_values)
      return face

   def yield_crops(self):
      self.crops += self.fertility
      if self.crops > 9:
         self.crops = 9

   def seed_me(self):
# vary from tile default values
# this will create an interesting board
      self.minerals += zero_bound(random.randint(-10,self.mine_max))
      self.fertility += zero_bound(random.randint(-7,3))
      self.crops += zero_bound(random.randint(-11,9))

# end of Tile
######################################################
class Row(object):
   'base class for a row of tiles'
   def __init__(self,width):
      self.strip = []
      self.width = width
      for i in range(width):
         self.strip.append(Tile())

   def rawdump(self):
      'used for the shell version of game - deprecated' 
      for i in range(self.width):
         self.strip[i].rawdump()
      print ''

   def dump_proximity(self,y,viz=2):
      'used for the shell version of game - deprecated' 
      low_col = zero_bound(y-viz)
      hi_col = upper_bound(y+viz,len(self.strip)-1)
      for i in range(low_col,hi_col+1):
         sys.stdout.write('Co%02d|' % i) 
         self.strip[i].rawdump()
# end of Row
######################################################
class SaveableBoard(db.Model):
   'shim used to hold a board for the datastore'
   stored_board = db.BlobProperty()
   name = db.StringProperty() # use this as a key for stored boards

   def decant(self):
      'return an object of type Board or None on exception'
      try:
         newboard = pickle.loads(self.stored_board)
      except pickle.PickleError:
         return None
      return newboard
# end of Saveable Board
######################################################
class Board(object):
   'base class for a gameboard'

   def __init__(self,width,rowcount):
      # dunno why we're using these next two fields
      self.playername = 'bob'  # dunno why we're using this...
      self.player = None # this can turn into a list later on...

      self.board = [] # this will become an array of type Row
      self.rowcount = rowcount # useful for setting limits on the fly
      self.colcount = width # useful for setting limits on the fly
      self.clock = 0
      for row in range(rowcount):
         self.board.append(Row(width))

   def yield_crops(self):
      for r in self.board:
         for t in r.strip:
            t.yield_crops()

# save the board into a form that can be stored  in the DB
   def preserve(self,sboard):
      try:
         sboard.stored_board = pickle.dumps(self)
      except pickle.PickleError:
         return None
      return sboard

# returns a tile when given an x,y position
   def get_tile_bypos(self,x,y):
      if (x<0 or x>=self.colcount) or (y<0 or y>self.rowcount):
         return None
      return self.board[y].strip[x]

   def place_me (self,p):
      spot = self.get_tile_bypos(p.here_x,p.here_y)
      if spot == None:
         return False
      else:
         r = spot.add_player(p) 
         return r

#end of Board
######################################################

# game global functions

def dice(n_sides):
   'returns the value of a dice roll with n_sides'
   return random.randint(1,n_sides)

def mdice(n,n_sides):
   'returns the result from n dice, with n_sides'
   tableau = [] # a list to hold the results
   for d in range(1,n+1):
      tableau.append(dice(n_sides))
   return tableau
      
def getboard(n):
   'retrieve a board from the datastore belonging to name'
   q = SaveableBoard.gql('WHERE name = :1', n)
   r = q.fetch(10)
   if r:
      return r[0]
   else:
      return None

def getaccount(n):
   pass
def getplayer(n):
   'given a name string, retrieve a player from the datastore'
   q = SaveablePlayer.gql('WHERE name = :1', n)
   r = q.fetch(10)
   if len(r) > 0:
      return r[0]
   else:
      return None

# call this to make a new Player object
def newplayer(nm,hx=2,hy=2,c=30,m=5): 
   'call this to make a new Player object'
   #call up user profile
   myprofile = users.get_current_user() 
   if not myprofile: 
      logging.error('we cannot create without login') 
      return (None,None)
   myuserid = myprofile.user_id()

   a = brainbank.getaccount(myprofile)

   p = Player(nm,hx,hy,c,m)
   logging.debug('new player built: name is %s' % p.name)
   return (p,a)

# deprecate or fix it
# this entry point allows command-line access to the game for
# testing purposes. crude, but effective for checking new logic
def main(): 
# make a board of 8x8
   brows = 8
   bcols = 8
   b = Board(bcols,brows) # build a simple board
   p = Player('Harry',3,3)
   while (1) : shell(b,p) # invoke command processor

# end of main()
if __name__ == "__main__": 
   main()

#######################################################
joblist = """
   add code to start new game
   add code to use up crops for moving
   add help system to explain game better
   normlize the status report by using a template
   add code to store player results in a global scoreboard
   revise the tile display to make it more attractive
   revise the command processor to run form working instance
   collapse move code using vector of lambda functions
"""
