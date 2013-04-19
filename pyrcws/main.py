# coding: utf-8
import logging
import urllib
import urllib2
from suds import WebFault
from suds.client import Client
from util import moneyfmt


# logging.basicConfig(level=logging.INFO)
# logging.getLogger('suds.client').setLevel(logging.DEBUG)
# logging.getLogger('suds.transport').setLevel(logging.DEBUG)
# logging.getLogger('suds.xsd.schema').setLevel(logging.DEBUG)
# logging.getLogger('suds.wsdl').setLevel(logging.DEBUG)


# URLS config
# service
SERVICE_URL = 'https://ecommerce.redecard.com.br/pos_virtual/wskomerci'  # remove trailing slash
# sandbox false
SOAP_URL = '%s/cap.asmx' % SERVICE_URL
WSDL_SOAP_URL = '%s?wsdl' % SOAP_URL
# sandbox true
SOAP_URL_TEST = '%s/cap_teste.asmx' % SERVICE_URL
WSDL_SOAP_URL_TEST = '%s?wsdl' % SOAP_URL_TEST
# return
RECEIPT_URL = 'https://ecommerce.redecard.com.br/pos_virtual/cupom.asp'


DEFAULT_TRANSACTION_TYPE = 'shop'
TRANSACTION_TYPE = {
    'cash': '04',
    'customer': '06',
    'shop': '08',
}


class GetAuthorizedException(Exception):
    def __init__(self, codret, msg):
        self.codret = codret
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class PaymentAttempt(object):
    '''
    affiliation_id: your affiliation code at redecard
    transaction: transaction type (check TRANSACTION_TYPE)
    total: total amount, including shipping and taxes (Decimal instance)
    installments: number of installments (1 is "cash")
    order_id: your order_id
    card_number: full card number without spaces (eg 1234567890123456)
    cvc2: cards cvc2
    exp_month: expiration month
    exp_year: expiration year (eg 2010)
    card_holders_name: as on card
    '''

    def __init__(self, affiliation_id, total, installments, order_id, card_number, cvc2,
            exp_month, exp_year, card_holders_name, transaction=None, debug=False):

        assert installments in range(1, 13), u'installments must be a integer between 1 and 12'

        assert (installments == 1 and (transaction == 'cash' or transaction is None)) \
            or installments > 1 and transaction != 'cash', \
            u'if installments = 1 then transaction must be None or "cash"'

        if installments == 1:
            transaction = 'cash'
            installments = '00'
        else:
            installments = str(installments).zfill(2)

        if not transaction:
            transaction = TRANSACTION_TYPE[DEFAULT_TRANSACTION_TYPE]
        else:
            transaction = TRANSACTION_TYPE[transaction]

        self.affiliation_id = affiliation_id
        self.transaction = transaction
        self.total = moneyfmt(total)

        self.installments = installments
        self.order_id = order_id
        self.card_number = card_number
        self.cvc2 = cvc2
        self.exp_month = exp_month
        self.exp_year = exp_year
        self.card_holders_name = card_holders_name

        self.client = self._get_connection(debug)
        self._authorized = False

        self.debug = debug

    def _get_connection(self, debug=False):
        if debug:
            return Client(WSDL_SOAP_URL_TEST, location=SOAP_URL_TEST, cache=None)
        return Client(WSDL_SOAP_URL, location=SOAP_URL, cache=None)

    def _get_total(self):
        # sandbox transactions must be total = 0.01
        if self.debug:
            return '0.01'
        return self.total

    def get_authorized(self, pax1='', pax2='', pax3='', pax4='',
            numdoc1='', numdoc2='', numdoc3='', numdoc4='', iata='', conftxn='N',
            concentrador='', entrada='', distribuidor='', taxaembarque='', adddata=''):

        args = (self._get_total(), self.transaction, self.installments, self.affiliation_id, self.order_id,
                self.card_number, self.cvc2, self.exp_month, self.exp_year, self.card_holders_name,
                iata, distribuidor, concentrador, taxaembarque, entrada, numdoc1, numdoc2,
                numdoc3, numdoc4, pax1, pax2, pax3, pax4, conftxn, adddata)

        if self.debug:
            try:
                ret = self.client.service.GetAuthorizedTst(*args)
            except WebFault, e:
                raise GetAuthorizedException(0, 'Webfault. %s' % e)
        else:
            ret = self.client.service.GetAuthorized(*args)

        self.codret = int(ret.AUTHORIZATION.CODRET or 0)
        self.data = ret.AUTHORIZATION.DATA
        self.numsqn = ret.AUTHORIZATION.NUMSQN
        self.numcv = ret.AUTHORIZATION.NUMCV
        self.numautor = ret.AUTHORIZATION.NUMAUTOR
        self.numpedido = ret.AUTHORIZATION.NUMPEDIDO
        self.msgret = urllib.unquote_plus(ret.AUTHORIZATION.MSGRET or '')
        self.card_number = '*' * 12 + self.card_number[-4:]  # keep only the last 4 digits
        self._authorized = True

        if self.codret:
            raise GetAuthorizedException(int(self.codret), self.msgret)

        return True

    def capture(self, pax1=None, pax2=None, pax3=None, pax4=None,
                numdoc2=None, numdoc3=None, numdoc4=None, adddata=None):

        assert self._authorized, u'get_authorized(...) must be called before capture(...)'

        args = (self.data, self.numsqn, self.numcv,
                self.numautor, self.installments, self.transaction, self._get_total(), self.affiliation_id,
                '', self.order_id, self.order_id, numdoc2, numdoc3, numdoc4, pax1,
                pax2, pax3, pax4, adddata)

        if self.debug:
            try:
                ret = self.client.service.ConfirmTxnTst(*args)
            except WebFault, e:
                raise GetAuthorizedException(0, 'Webfault. %s' % e)
        else:
            ret = self.client.service.ConfirmTxn(*args)

        if int(ret.CONFIRMATION.CODRET) in (0, 1):
            return True
        return False

    def get_receipt_html(self):
        values = {
            'DATA': self.data,
            'TRANSACAO': self.transaction,
            'NUMAUTOR': self.numautor,
            'NUMCV': self.numcv
        }

        req = urllib2.Request(RECEIPT_URL, urllib.urlencode(values))
        response = urllib2.urlopen(req)
        return response.read()
