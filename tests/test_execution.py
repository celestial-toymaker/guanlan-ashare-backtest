from decimal import Decimal as D

from ashare_bt.execution import Broker, ExitPlanner
from ashare_bt.ledger import Ledger
from ashare_bt.rules import FeeModel, candidate_limits, legal_quantity


def setup(market):
    config,data,features,status = market
    row = data.date_index[config.start] - 1
    ledger = Ledger(config.initial_cash, day=data.dates[row])
    return Broker(config,data,features,status,ledger),row


def test_next_open_cash_capacity_expiry_and_cancel(market):
    broker,row = setup(market)
    broker.config.participation = "0.00001"
    orders = broker.submit("000001.SZ","buy",100000,row,row+1)
    assert broker.ledger.frozen > 0
    broker.ledger.day = broker.data.dates[row+1]
    broker.match_open(row+1)
    assert orders[0].status == "expired" and 0 < orders[0].filled < 100000
    assert D(broker.trades[0]["notional"]) <= 10000
    assert broker.ledger.frozen == 0
    new = broker.submit("600001.SH","buy",100,row+1,row+2)[0]
    rebuilt = broker.replace(new.order_id,200,row+1,row+2)
    assert new.status == "cancelled" and rebuilt[0].quantity == 200
    broker.cancel(rebuilt[0].order_id)
    broker.ledger.assert_invariants()


def test_blocked_open_then_intraday_opening_and_zero_amount(market):
    broker,row = setup(market)
    data = broker.data
    previous = data.arrays["close"][row,0]
    upper = D(candidate_limits("000001.SZ",data.dates[row+1],previous,is_st=False)[0]["upper"])
    data.arrays["open"][row+1,0] = float(upper)
    data.arrays["low"][row+1,0] = previous
    order = broker.submit("000001.SZ","buy",100,row,row+1)[0]
    broker.ledger.day = data.dates[row+1]
    broker.match_open(row+1)
    assert order.filled == 0 and "候选涨停" in order.last_reason
    data.arrays["amt"][row+2,0] = 0
    order = broker.submit("000001.SZ","buy",100,row+1,row+2)[0]
    broker.match_open(row+2)
    assert order.filled == 0 and "成交额" in order.last_reason


def test_t1_st_open_recheck_and_quantity_rules(market):
    broker,row = setup(market)
    broker.status.open_values[row+1,0] = 1
    order = broker.submit("000001.SZ","buy",100,row,row+1)[0]
    broker.ledger.day = broker.data.dates[row+1]
    broker.match_open(row+1)
    assert order.filled == 0 and "非 ST" in order.last_reason
    broker.ledger.buy("000001.SZ",100,10,{},broker.data.dates[row+2])
    assert broker.ledger.positions["000001.SZ"].sellable(broker.data.dates[row+1]) == 0
    assert broker.ledger.positions["000001.SZ"].sellable(broker.data.dates[row+2]) == 100
    assert legal_quantity("688001.SH",201,"buy") == 201
    assert legal_quantity("000001.SZ",201,"buy") == 200
    assert legal_quantity("000001.SZ",37,"sell",37) == 37


def test_fees_and_history_bands(market):
    config,*_ = market
    fees = FeeModel(config).quote("600001.SH","2025-01-02","sell",10000)
    assert fees == {"commission":D(5),"stamp_tax":D(5),"transfer":D("0.10"),"slippage":D(5)}
    assert candidate_limits("600001.SH","2026-07-03",10,is_st=True)[0]["upper"] == "10.50"
    assert candidate_limits("600001.SH","2026-07-06",10,is_st=True)[0]["upper"] == "11.00"
    assert candidate_limits("300001.SZ","2025-01-02",10,is_st=True)[0]["upper"] == "12.00"


def test_exit_planner_uses_known_capacity(market):
    broker,row = setup(market)
    planner = ExitPlanner(broker.config,broker.data,broker)
    first = planner.estimate("000001.SZ",100000,row)
    broker.data.arrays["amt"][row+1:,0] *= .0001
    second = planner.estimate("000001.SZ",100000,row)
    assert first == second
