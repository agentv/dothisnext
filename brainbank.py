from google.appengine.ext import db
from google.appengine.api import users

import logging

"""
Brainbank module:

defines these elements:

   BankAccount (db.Model)
   AccountPool (contains list of Account objects)
   BankOperator (entity which may request Bank operations)
   PoolManager (encapsulates legal operations on AccountPool objects)
   Transaction (encapsulates an operative request on the Bank)
      transtype - deposit
      transtype - charge
      transtype - newaccount
      transtype - closeaccount
      transtype - adjustaccount

   CentralBank (encapsulates authenticity and authority operations)
   AuthKey
      keytype - manager
      keytype - staff
      keytype - customer
      keytype - viewer
      keytype - auditor
   Report
      reporttype - account summary
      reporttype - pool summary
      reporttype - manager pools

"""
##############################################
class BankAccount(db.Model):
   'base class for accounts'
   id = db.StringProperty() # required = True
   owner = db.StringProperty() # required = True
   balance = db.IntegerProperty()
   pool_membership = db.StringProperty()
   ownername = db.StringProperty()

   acct_agreement = """
   This account is for FUN and you may only use it as long as
   you are HAVING FUN. If that fails to be the case, the account
   will dissolve and you will no longer be having fun.
   We would INTERPRET your intention to bring lawsuit, complain
   about anything whatsoever, or to harm us knowingly, to be
   evidence that you are not having fun and we will DISSOLVE your
   account.

   So Have Fun!

   """

   def credit(self,amt):
      self.balance += amt
      self.put()

   def debit(self,amt):
      self.balance -= amt
      self.put()

   def validate(self):
      """ensure that all fields are populated"""
      if not self.id: # here comes a hack. validate acct earlier than this
         self.id = ''
      if not self.owner:
         self.owner = ''
      if not self.ownername:
         self.ownername = 'Alan Smithee'
      if not self.balance:
         self.balance = 0
      self.put()

   def statement(self):
      self.validate()
      return ('%s: %s: %d' % (self.id, self.ownername, self.balance))

   def print_agreement(self):
      return acct_agreement

##############################################
class AccountPool(object):
   """
   a set of accounts, sort of like a Branch

   contains a 'library' - a set of accounts
   encapsulates a manager authorized to 'work the pool'

   Example:
      ap = AccountPool('poolid','poolname') # also (operator,authkey) in future
      for a in acct_sequence:
         ap.add_account(a)
      print ap.report_pool()

   """
   def __init__(self,poolid,poolname):
   #def __init__(self,o,authkey):
      """
      under best conditions, this constructor may
      only be called by the CentralBank

      provide:
         str poolid
         str poolname

      Soon you must call it with an operator (o) and a
      valid AuthKey (authkey) for it to work out
      """
      # future: check key for authority using o and authkey
      self.id = poolid
      self.name = poolname
      self.acct_library = []
      self.manager = PoolManager(poolid)
      self.manager.set_pool(self)

   def report_pool(self):
      'return a string with report from all accounts in pool'
      r = ''
      for a in acct_library:
         # use a to get account from datastore
         q = BankAccount.gql('WHERE id = :1', a)
         result = q.fetch(1)
         acct = result[0]
         r += '%s\n' % acct.statement()
      return r

   def add_account(self,a):
      'add the account id to the library or account map'
      self.acct_library.append(a.id)


##############################################
class PoolManager(object):
   'contains business rules for using AccountPool'

   def __init__(self,name):
      """
      provide:
         manager name
      after initialization:
         mgr.set_pool(p)
      """
      self.name = name

   def set_name(self,name):
      self.name = name
   def set_pool(self,pool):
      self.pool = pool

   def report_all_pool_accounts(self):
      'list each account: return as string'
      report = ''
      for acct in self.pool.acct_library:
         # find acct from account number
         q = BankAccount.gql('WHERE id = :1', acct)
         result = q.fetch(1000) 
         # append acct info to result string
         for a in result:
            report += '%s: %s --> %d', (a.id,a.owner,a.balance)
      return report
          
   def summarize_pool(self):
      'list pool statistics: return as string'
      return 'Pool %s: %s\n' % (p.id,p.name)
         
   def conduct_transaction(self,trans,o):
      """
      honor transactions sent from customer operator
      and automatic transactions from a queue
      1) validate transaction
      2) select account
      3) apply transaction
      4) report success
      """
      pass
##############################################
class AuditRecord(db.Model):
   """ signature is ipaddr/timestamp hash """
   signature = db.StringProperty()
   datestamp = db.DateTimeProperty(auto_now_add=True)
   remark = db.TextProperty()

   def make_signature(self,name):
      signature = '%s:%s' % (self.datestamp.time(), name)

##############################################
class Transaction(AuditRecord):
   opcode = db.StringProperty()
   acct_name = db.StringProperty()


##############################################
class BankOperator(db.Model):
   'object saves state of an actor in the bank'
   id = db.StringProperty()
   name = db.StringProperty()
   authority = db.StringProperty()

##############################################

class CentralBank(object):
   """
   where all the money comes from

   This class implements the major operations that occur with respect
   to the bank. This gives us the methods to open and close a branch,
   to initialize a branch, this is the granting authority for security
   keys and the authentication agent
   
   Example use:

      central = CentralBank()
      central.initiate_branch()
   """
   first_seed = 10000000L
   next_acctno_seed = 20100101
   def __init__(self):
      '''
      opening a Central Bank is a big damn deal. 
      you should be a king or better
      '''

   def new_acctno(self,pool):
      n = pool.id + str(CentralBank.next_acctno_seed)
      CentralBank.next_acctno_seed += 1
      return n # although we MIGHT consider sanity checking the number in here

   def open_branch(self,pool):
      'routine to open a branch'
      pool.currently_open = True
   def close_branch(self,pool):
      'routine to close a branch'
      pool.currently_open = False

   def initiate_branch(self,poolid,poolname):
# insert latch here to check authority
      pool = AccountPool(poolid,poolname)
      pool.reserve_fund = first_seed
      pool.founding_date = time.time()
      pool.currently_open = True
      return pool

   def become_operator(self,id):
      """
      Give us a user id, and we'll get you set up to use
      the bank.

      Use this method to become an operator of some sort in the bank
      this is equivalent to a login method. we grant them an operator 
      identity in the system

      We'll do these things:

         use your userid to look up an existing operator badge in the system
         make a guest badge for you if none exists
      """
      q = BankOperator.gql('WHERE id = :1', id)
      results = q.fetch(1)
      if results:
         return results[0]
      else:
         o = self.create_operator(id)
         return o

   def create_operator(self,userid):
      'return existing account if one exists, or create a new one'
      """
      if userid matches existing operator record:
         get the existing operator record
         write to audit trail - attempt to create for existing
         return existing record
      else:
      """
      o = BankOperator(id=userid,authority='guest')
      o.put()
      # leave audit record about the new operator id

   def promote_operator(self,o,level):
      admin_operators = ['agentv']
      # we should check first to see if we want to grant the 
      # requested authority
      o.authority = level
      # leave an audit trail about the authority changhe

   def grant_key(self,o,keytype):
      """
      keys are granted by this authority, and validated when they are
      used. There are five types of keys available,
            manager: full read/write authority across bank
            auditor: full read authority across bank
            staff: authority as rationalized by business rules
            customer: signficant read authority across some accounts
            guest: limited authority
      keys of any given type may have differing characteristics. They
      all share these:"
         creation timestamp
         authentication key
         expiration time
      """
      type_table = {
         'manager': managerkey,
         'auditor': managerkey,
         'staff': managerkey,
         'customer': customerkey,
         'guest': guestkey,
      }
# test for legal keytype
      try:
         k = type_table[keytype]
      except Exception:
         return None
      return k

      # call creator method for keytype
      def guestkey(self,o):
         k = AuthKey()
         k.operator = o
         k.type='guest'
         k.expiration = -1
         k.timestamp = 1 # get a real timestamp here
         return k

      def customerkey(self,o):
         k = self.guestkey(o)
         k.customerid = '' # get it from a legal place
         k.type = 'customer'
         return k

      def managerkey(self,o):
         k = self.guestkey(o)
         k.managerid = '' # get this from a legal source
         k.type = 'manager'
         return k

class AuthKey(object):
   """
   This object serves to regulate transactions and authority
   within the banking system. Only the CentralBank can grant
   or authenticate keys of this type
   """
   def __init__(self):
      self.type='' 
      self.operator = None

def getaccount(user):
   """
   This global method returns a BankAccount object
   for the current user. If no user is logged in, this
   method returns None. If no account exists, this
   will create an account and 'seed' it with 150 brainbucks
   
   """
   id = user.user_id() 
   name = user.nickname()
   email = user.email()

   logging.info('lookup account for %s %s %s' % (id,name,email))
   # we're using id to get the account 
   q = BankAccount.gql('WHERE owner = :1', id) 
   r = q.get()
   logging.info('after datastore query, we have %s' % r)
   if r:  # they have a bank account 
      return r
   else: # we have to make them a new one 
      b = BankAccount(
         id=id, # here's where we'd construct good acct numbers
         owner=id,
         balance=150,
         ownername = user.nickname()
      ) 
      b.put()
      return b

