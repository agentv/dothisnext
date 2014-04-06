import os, logging, cgi
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.ext import db

import tycoon # our easter egg
import brainbank

class TycoonScoreboard(webapp.RequestHandler):
   """
   display top scores for Tycoon

   Right now, this method expects to be sent info about the results
   of a recently completed game.  Later we should isolate that.
   It should be possible to get a Hall of Fame at any time.
   """
   def get(self):
      'Scoreboard Handler'
      myname = 'anonymous'
      url = '/'
      url_linktext = 'Logout'
      myacct = {}

      iam = users.get_current_user()
      if iam:
         myname = iam.nickname()
         url = users.create_logout_url(self.request.uri)
      else:
         self.redirect('/')
         #self.redirect(users.create_login_url(self.request.uri))

# we'll pull this user's bank account info
      a = brainbank.getaccount(iam)
      myacct['name'] = myname
      myacct['balance'] = a.balance

# let's see what they sent me...
      pname = myname; pname = self.request.get('name')
      worth = 0; worth = self.request.get('worth')
      ratio = 0.0; ratio=self.request.get('ratio')
      myscore = {'name':pname,'score':worth,'efficiency':ratio}
# now let's get the hall of fame info
      q = tycoon.ScoreLine.all().order('-yield_ratio')
      bestscores = q.fetch(12)

      template_values = {
         'myname': myname,
         'myacct': myacct,
         'url': url,
         'url_linktext': url_linktext,
         'myscore': myscore,
         'bestscores': bestscores,
      }
      path=os.path.join(os.path.dirname(__file__), 'scoreboard.html')
      self.response.out.write(template.render(path,template_values))


class Tycoon (webapp.RequestHandler):
   'request handler for the Tycoon game'
   def get_player(self,name):
      """
      We are returning a player carton (splayer), a player (tplayer),
      a board carton (sboard), and a board (tboard)
      """
# get the player from the datastore  with the current playername
      p = tycoon.getplayer(name)

      if p != None:
         #use that player
         tplayer = p.decant()
         # get a board with the current playername
         b = tycoon.getboard(tplayer.name)
         # if that fails, make a new board using current player
         if b != None:
            # grab this instance for use...
            tboard = b.decant()
            tplayer.board = tboard
         else:
            b = tycoon.SaveableBoard(name=tplayer.name)
            tboard = tycoon.newboard(tplayer.name,10,6) # update!
            tboard.place_me(tplayer) # check return required for multiplayer
            tplayer.board = tboard
      # if that fails, make a new player
      else:
         p = tycoon.SaveablePlayer(name=name)
         b = tycoon.SaveableBoard(name=name)
         (tplayer,bank_account) = tycoon.newplayer(name) 
         tboard = tycoon.newboard(tplayer.name)
         tboard.place_me(tplayer)
         tplayer.board = tboard
      return (p,tplayer,b,tboard)

   def get(self):
# these must be set to satisfy parser
      myname = 'anonymous' 
      url = '/'
      url_linktext = 'Logout'
# establish the Logout prompt, ensure that they're logged in here...
      iam = users.get_current_user()
      if iam:
         myname = iam.nickname()
         url = users.create_logout_url(self.request.uri)
      else:
         self.redirect(users.create_login_url(self.request.uri))
      (splayer,tplayer,sboard,tboard) = self.get_player(myname)

# process any commands that exist
      #check for commands
      cmd = self.request.get('cmd')
      direction = self.request.get('direction')
      if direction:
         tplayer.direction = direction
         cmd = 'move'
      else:
         tplayer.direction = ''
      #process legal commands
      cp = tycoon.CommandProcessor()
      r = cp.process_cmd(cmd,tplayer,tboard)

      if r != 'game over': # I now officially hate negative logic too!
         # or else, keep playing
         if r != '': 
            g = Greeting(author=users.User("tycoon@gmail.com"),content=r) 
            g.put()
   
         # store board and player back in the db
         sp = tplayer.preserve(splayer)
         sp.put()
   
         sb = tboard.preserve(sboard)
         if sb == None:
            logging.error('cannot save the game player')
         else: 
            sb.put()
   
   # now, assemble the response object - first, gather the chatter stream
         greetings_query = Greeting.all().order('-date')
         greetings = greetings_query.fetch(6)
         greetings.reverse()
   # a player status card
         rendered_status = tplayer.render()
# now the backstory at last
         template_values = { }
         path=os.path.join(os.path.dirname(__file__), 'backstory.html')
         backstory = template.render(path,template_values)
         gameclock = tboard.clock
   # pass all that to the template
         template_values = {
            'backstory': backstory,
            'gameclock': gameclock,
            'tycoon_board': tboard,
            'tycoon_status': rendered_status,
            'greetings': greetings,
            'myname': myname,
            'url': url,
            'url_linktext': url_linktext,
         }
         path=os.path.join(os.path.dirname(__file__), 'tycoon.html')
         self.response.out.write(template.render(path,template_values))

      else:
         # game over - it ends here!
         #pay 'em for playing
         a = brainbank.getaccount(iam)
         if a:
            a.credit(5) # constant again!
         # calculate final score
#this formula needs to be extracted and delegated to a scoring routine
         # constant alert!
         total_worth = tplayer.crops * 2 + tplayer.minerals * 5
         yield_ratio = float(total_worth) / float(tboard.clock)

         # store it in the datastore
         boxscore = tycoon.ScoreLine()
         boxscore.name = tplayer.name
         boxscore.total_worth = total_worth
         boxscore.yield_ratio = yield_ratio
         boxscore.put()
         # destroy player and board records in datastore
         splayer.delete()
         sboard.delete()

         # plant game statistics in a command
         score_values = 'worth=%d&ratio=%5.3f&name=%s' % \
            (total_worth,yield_ratio,tplayer.name)
         final_url = '/tycoonscoreboard?%s' % score_values
         # and redirect to a final wrap-up page
         self.redirect(final_url)
   # end of get() methoc
# end of Tycoon
##############################################
class Help (webapp.RequestHandler):
   'response class to display help page'
   def get(self): 
# gather the chat stream
      greetings_query = Greeting.all().order('-date')
      greetings = greetings_query.fetch(12)
      greetings.reverse()
# establish the Login/Logout prompt
      iam = users.get_current_user()
      if iam:
         myname = iam.nickname()
         url = users.create_logout_url(self.request.uri)
         url_linktext = 'Logout'
      else:
         myname = 'anonymous'
         url = users.create_login_url(self.request.uri)
         url_linktext = 'Login'
# pass all that to the template
      template_values = {
         'greetings': greetings,
         'myname': myname,
         'url': url,
         'url_linktext': url_linktext,
      }
      path=os.path.join(os.path.dirname(__file__), 'help.html')
      self.response.out.write(template.render(path,template_values))
# end of Help
##############################################
class UserPrefs(db.Model):
   'object saves state between views of the table'
   owner = db.StringProperty()
   sort_order = db.StringProperty()
   page_size = db.IntegerProperty()

##############################################
class TaskTable(object):
   'class to display tasks in a table'
   def render(self):
      'return a string with the HTML to provide the task table'
      pass
##############################################
class MainPage(webapp.RequestHandler): 
   'Main Page rendering class'
   def get(self): 

      iam = users.get_current_user()
      if iam:
         myname = iam.nickname()
      else:
         myname = 'anonymous'
         self.redirect(users.create_login_url(self.request.uri))

      pquery = UserPrefs.gql('WHERE owner = :1', myname)
      results = pquery.fetch(1)
      if results: 
         prefs_obj = results[0]
      else:
         prefs_obj = UserPrefs(page_size=50,sort_order='priority') 
         prefs_obj.owner = myname

# gather the task stream
# if a sort order is indicated, use that, and alter the sort order
      sort_order = self.request.get('sort_order')
      if sort_order: 
         if sort_order in prefs_obj.sort_order:
            if prefs_obj.sort_order.startswith('-'):
               pass
            else:
               sort_order = "-" + prefs_obj.sort_order
         prefs_obj.sort_order = sort_order
      alltasks = self.gather_tasks(prefs_obj.sort_order,prefs_obj.page_size)

# assemble the task table

# gather the chat stream
      greetings_query = Greeting.all().order('-date')
      greetings = greetings_query.fetch(10)
      greetings.reverse()

# establish the Login/Logout prompt
      url = users.create_logout_url(self.request.uri)
      url_linktext = 'Logout'

      prefs_obj.put() # save the prefs for next visit
      template_values = {
         'greetings': greetings,
         'tasklist': alltasks,
         'url': url,
         'myname': myname,
         'url_linktext': url_linktext,
      }
      path=os.path.join(os.path.dirname(__file__), 'index.html')
      self.response.out.write(template.render(path,template_values))

   def gather_tasks (self,sort_order,page_size):
      'grab tasks using the indicated sort_order - returns a result set'
      task_query = DTN_Task.all().order(sort_order)
      results = task_query.fetch(page_size)
      for item in results:
         item.description = item.description[:80]
         item.status = item.status[2:]
      return results

##############################################
class Greeting (db.Model):
   'data model for chat entry'
   author = db.UserProperty()
   content = db.StringProperty(multiline=True)
   date = db.DateTimeProperty(auto_now_add=True)

##############################################
class Guestbook(webapp.RequestHandler): 
   def post(self): 
      greeting = Greeting()
      if users.get_current_user(): 
         greeting.author = users.get_current_user()
      greeting.content = self.request.get('content')
      greeting.put()
      self.redirect('/')

##############################################
class DTN_Task (db.Model): 
   'datamodel class for DoThisNext'
   name = db.StringProperty()
   priority = db.StringProperty()
   due_date = db.DateTimeProperty(auto_now_add=True)
   description = db.TextProperty()
   tags = db.StringListProperty()
   creator = db.StringProperty()
   owner = db.StringProperty()
   status = db.StringProperty()
# end of Task data model definition
##############################################
class TaskDelete(webapp.RequestHandler):
   'delete a specific task from the database'
   def post(self):
      key = self.request.get('key')
      if not key:
         self.redirect('/')
      task = DTN_Task.get(key)
      task.delete()
      self.redirect('/')
##############################################
class TaskUpdate(webapp.RequestHandler):
   'update the task in the datastore'
   def post(self):
      key = self.request.get('key')
      if not key:
         self.redirect('/')
      task = DTN_Task.get(key)
      task.name = self.request.get('taskname')
      task.priority = self.request.get('priority')
      task.description = self.request.get('description').strip()
      task.owner = self.request.get('owner')
      allcats = self.request.get('category').split(',')
      cleancats = []
      for cat in allcats:
         cleancats.append(cat.strip())
      task.tags = cleancats
      task.status = self.request.get('status')
      task.put()
      self.redirect('/')

##############################################
class TaskInput(webapp.RequestHandler): 
   'request handler class for DoThisNext'
   def post(self): 

      task = DTN_Task()
# input fields: taskname, priority, description, category,
# due_date, owner, status
      creator = users.get_current_user()
      if creator: 
         task.creator = creator.nickname()
      else:
         task.creator = 'anonymous'
      task.name = self.request.get('taskname')
      if task.name == '':
         task.name = 'unnamed task'
# priority values: 1 2 3 4 5
      task.priority = self.request.get('priority')
      task.description = self.request.get('description')
      task.owner = self.request.get('owner')
      cat = self.request.get('category')
      allcats = cat.split(',')
      cleancats = []
      for cat in allcats:
         cleancats.append(cat.strip())
      task.tags = cleancats
# status values: Opened Acknowledged Working Complete Archived
      task.status = self.request.get('status')
      task.put()
      self.redirect('/')

##############################################
class DropTasks(webapp.RequestHandler):
   'handler for zeroing the task database'
   def get(self):
      q = DTN_Task.all()
      for t in q:
         t.delete()
      self.redirect('/')

##############################################
class DropMessages(webapp.RequestHandler):
   'handler for zeroing the message database'
   def get(self):
      q = Greeting.all()
      for g in q:
         g.delete()
      self.redirect('/')

##############################################
class BrainBank(webapp.RequestHandler):
   '''
   handle brainbank transaction

   accept transaction request
   parse request
   execute (with proper authority)

   transactions:
      create account
      f- archive account
      f- deposit to account
      f- debit account
      account status

   class methods:
      account_agreement()
      account_fees()
   '''

   def get(self):
      iam = users.get_current_user()
      if not iam:
         logging.error('bank login attempt: no identity')
         self.redirect('/brainbank')
      myname = iam.nickname()
      myuserid = iam.user_id()
      #o = brainbank.CentralBank().become_operator(myuserid)

      q = brainbank.BankAccount.gql("Where owner = :1",myuserid)
      r = q.fetch(1)
      if r:
         acct = r[0]
      else:
         acct = None

      cmd = self.request.get('cmd')
      body = '&nbsp;'
      # Somewhere in this mess, we'll populate 'body'
      if not cmd:
         body = """
         Brainbucks Mutual Bank welcomes %s!
         """ % myname
      else:
         if cmd == 'statement':
            if acct:
               body = """
               <pre>
               Account Balance: %d
               </pre>
               """ % acct.balance
            else:
               body = """
               <pre>
               Set up an account today!
               </pre>
               """
         elif cmd == 'looptest':
            body = """
            <pre>
            Reporting on all Messages
            %s\t%s\t%s
            """ % ('Account','Owner','Balance')
            q = Greeting.all()
            records = q.fetch(1000)
            if (records):
               for i in range(0,len(records)): #try while (record = records.pop()):
                  record = records[i] 
                  body += '%d: %s: %s\n' % \
                     (record.key().id(),record.author,record.content) 
            body += '</pre>'

# this section should be a method in the brainbank module
# probably should be a part of the PoolManager operations
         elif cmd == 'reportall':
            q = brainbank.BankAccount.all()
            resultset = q.fetch(50) # extend this to deal with multi-pages
            template_values = {
               'resultset': resultset
            }
            path=os.path.join(os.path.dirname(__file__), 'accountsummary.html')
            body = template.render(path,template_values)

         elif cmd == 'newacct':
            # this routine is meant to add new accounts but it
            # cannot really do so because new user accounts are
            # fake on the dev server.

            """
            holder = self.request.get('holder')
            if holder:
               u = users.User(holder)
               logging.info('new user object for: %s' % u.nickname() + ' ')
               a = brainbank.getaccount(u)
               logging.info('account created: %s' % a.id + ' ')
               pass
            else:
               pass # they don't really mean it 
            """
            self.redirect('/brainbank?cmd=reportall') 

         elif cmd == 'inherit':
            acct.credit(50)
            acct.put()
            self.redirect('/brainbank?cmd=statement') 
         
      # okay then, let's say what we're gonna say...
      template_values = { 
         'myname': myname, 
         'url': '/brainbank', 
         'url_linktext': 'Brainbank', 
         'pagebody': body 
      } 
      path = os.path.join(os.path.dirname(__file__), 'bankreport.html')
      self.response.out.write(template.render(path,template_values))

   def do_cmd(self,cmd):
      """
      command processor for banking
      accepts these commands:
         open account
         close account
         report pool
         report account
         adjust account
      """
      pass

# find an operator in the datastore with this identity
   manager_operator = """
   a manager may do anything that a guest may do plus:
      accept and execute a transaction from a customer
      report on managed pools
      report on accounts
      report on transactions
   """
   customer_operator = """
   a customer may do anything that a guest may do plus:
      submit transaction on account
      report on account
      report on transactions
   """
# if there is no operator for this user, then create a new guest operator

   guest_operator = """
   a guest may do these things in the bank:
      read bank info
      read bank policies
      read account policies
      establish an account
   """


##############################################
class WholeTask(webapp.RequestHandler):
   'displays the whole task for editing'
   def get(self):
      iam = users.get_current_user()
      if not iam:
         logging.error('we do not have an identity, myname is empty')
         self.redirect('/')
      myname = iam.nickname()
# establish the Login/Logout prompt
      url = users.create_logout_url(self.request.uri)
      url_linktext = 'Logout'

      item_key = self.request.get('key')
      if not item_key:
         self.redirect('/')

      item = DTN_Task.get(item_key)
      if not item:
         logging.error('attempt to get item with key %s failed...' % item_key)
         self.redirect('/')
# convert the tags set back into a string
      concat = ', '
      tags_string = concat.join(item.tags)
# convert the priority into a full widget for display         priority_widget = '<select name="priority"> '
      priority_widget = '<select name="priority">'
      for p in range(1,6):
         priority_widget += '<option value="%d"' % p
         if int(item.priority) == p:
            priority_widget += 'selected="selected"'
         priority_widget += '>%d</option>' % p
      priority_widget += '</select>'
# convert the status into a full widget for display
      status_types = ( "1-Opened", "2-Acknowledged", "3-Underway",
      "4-Complete", "5-Archived")
      status_widget = '<select name="status">'
      for s in status_types:
         status_widget += '<option value="%s"' % s
         if item.status == s:
            status_widget += ' selected="selected"'
         status_widget += '>%s</option>' % s[2:]
      status_widget += '</select>'

      template_values = {
         'item_key': item_key,
         'url': url,
         'url_linktext': url_linktext,
         'myname': myname,
         'item': item,
         'tags_string': tags_string,
         'priority_widget': priority_widget,
         'status_widget': status_widget,
      }
      path=os.path.join(os.path.dirname(__file__), 'taskview.html')
      self.response.out.write(template.render(path,template_values))

# remove the debug-True incantation for final deployment
application = webapp.WSGIApplication( 
   [
      ('/', MainPage), 
      ('/sign', Guestbook),
      ('/taskdelete', TaskDelete),
      ('/taskinput', TaskInput),
      ('/taskupdate', TaskUpdate),
      ('/tycoon', Tycoon),
      ('/brainbank', BrainBank),
      ('/tycoonscoreboard', TycoonScoreboard),
      ('/wholetask', WholeTask),
      ('/killmessages', DropMessages),
      ('/killtasks', DropTasks),
      ('/help', Help)
   ], debug=True)

def main(): 
   run_wsgi_app(application)

if __name__ == "__main__": 
   main()
