"""在指定 GPU 实机核对分块、检测、原始精度因子和动量入选排名。"""
from pathlib import Path
from types import SimpleNamespace
import argparse
import json

import numpy as np
import pandas as pd
import torch

from ashare_bt.config import Config
from ashare_bt.compute import compute_features
from ashare_bt.data import load_data, History
from ashare_bt.engine import eligibility
from ashare_bt.status import StatusProvider
from ashare_bt.strategies import SPECS, StrategyRegistry, stable_rank
from ashare_bt.utils import atomic_json


def reference_factors(data):
    """原始 float64 只承担验收基准，批量运行使用请求的 GPU。"""
    adjusted=data.arrays['close']*data.arrays['cumadj']
    prices=pd.DataFrame(adjusted)
    returns=prices.pct_change(fill_method=None)
    output={'ret_1':returns.to_numpy(),'adv_20':pd.DataFrame(data.arrays['amt']).rolling(20).mean().to_numpy()}
    for window in (5,10,14,20,60):
        output[f'mom_{window}']=prices.pct_change(periods=window,fill_method=None).to_numpy()
        output[f'ma_{window}']=prices.rolling(window).mean().to_numpy()
        output[f'std_{window}']=prices.rolling(window).std(ddof=0).to_numpy()
        output[f'vol_{window}']=returns.rolling(window).std(ddof=0).to_numpy()
        for field,operation in [('high','max'),('low','min')]:
            frame=pd.DataFrame(data.arrays[field]*data.arrays['cumadj']).rolling(window)
            output[f'{field}_prev_{window}']=getattr(frame,operation)().shift(1).to_numpy()
    changes=np.diff(adjusted,axis=0)
    gain=np.zeros(data.shape[1]);loss=gain.copy();count=np.zeros(data.shape[1],int)
    rsi=np.full_like(adjusted,np.nan)
    for row,change in enumerate(changes):
        valid=np.isfinite(change);count=np.where(valid,count+1,0)
        gain=np.where(valid,(gain*13+np.maximum(change,0))/14,0)
        loss=np.where(valid,(loss*13+np.maximum(-change,0))/14,0)
        seed=count==14
        if seed.any():
            recent=changes[row-13:row+1]
            gain[seed]=np.maximum(recent[:,seed],0).mean(axis=0)
            loss[seed]=np.maximum(-recent[:,seed],0).mean(axis=0)
        ratio=np.divide(gain,loss,out=np.zeros_like(gain),where=loss>0)
        score=np.where(loss>0,100-100/(1+ratio),np.where(gain>0,100,50))
        rsi[row+1]=np.where(count>=14,score,np.nan)
    output['rsi_14']=rsi
    return output


def validate(device="mps"):
    config=Config(device=device)
    data=load_data(config,lambda **r:print(r["message"],flush=True))
    main=compute_features(data,config,use_cache=True)
    checked={"device":main.metadata,"shape":data.shape,"checks":{},"cuda_hardware":torch.cuda.is_available(),
             "status_basis":"独立数值核对采用固定普通股票状态；正式回测另行审计历史 ST"}
    for block in (64,256):
        config.block_days=block
        other=compute_features(data,config,use_cache=False)
        for key in main.flags:
            assert np.array_equal(main.flags[key],other.flags[key]), (block,key)
        errors={key:float(np.nanmax(np.abs(main.values[key]-other.values[key]))) for key in main.values}
        assert all(error<.0003 for error in errors.values()), errors
        checked["checks"][f"block_{block}"]={"flags_equal":True,"max_absolute_error":errors}
    adjusted=data.arrays["close"]*data.arrays["cumadj"]
    exact=np.full_like(adjusted,np.nan)
    exact[20:]=adjusted[20:]/adjusted[:-20]-1
    error=np.nanmax(np.abs(exact-main.values["mom_20"]))
    assert error<2e-6,error
    checked["checks"]["momentum_float64_max_error"]=float(error)
    raw_changed=np.zeros(data.shape,bool)
    previous=np.full(data.shape[1],np.nan)
    for i,factor in enumerate(data.arrays["cumadj"]):
        valid=np.isfinite(factor)&(factor>0)
        raw_changed[i]=valid&np.isfinite(previous)&(factor!=previous)
        previous=np.where(valid,factor,previous)
    assert np.array_equal(raw_changed,main.flags["factor_change"])
    checked["checks"]["factor_changes_exact"]=int(raw_changed.sum())
    config.block_days=128
    status=StatusProvider.synthetic(data.dates,data.securities)
    mismatches=[]
    strategy=StrategyRegistry().create(config)
    for row in range(data.date_index[config.start]-1,len(data.dates)):
        eligible,reasons=eligibility(data,main,status,config,row)
        history=History(data,main,status,row,eligible,reasons)
        scores=strategy.score(history)
        ranked=strategy.refine_ranking(history,scores,stable_rank(scores,eligible,data.securities))
        exact_rank=stable_rank(exact[row],eligible,data.securities)
        if ranked[:20].tolist()!=exact_rank[:20].tolist():
            mismatches.append(data.dates[row])
    assert not mismatches,mismatches
    checked["checks"]["daily_top20_rank_exact"]=True
    checked["checks"]["arrow_missing_equal"]=True
    original=reference_factors(data)
    precision={}
    for key,values in original.items():
        actual=main.values[key]
        assert np.array_equal(np.isnan(values),np.isnan(actual)),key
        error=float(np.nanmax(np.abs(values-actual)))
        scale=float(np.nanmax(np.abs(values)))
        tolerance=.001 if key.startswith('rsi_') else max(2e-5,scale*3e-6)
        assert error<=tolerance,(key,error,tolerance)
        precision[key]={'max_absolute_error':error,'tolerance':tolerance}
    checked['checks']['float64_reference']=precision
    rank_checks={}
    for kind,key,sign in [('momentum','mom_20',1),('reversal','mom_5',-1),('low_volatility','vol_20',-1),('liquidity','adv_20',1)]:
        probe=StrategyRegistry().create(Config(device=device,strategy=kind))
        for row in range(data.date_index[config.start]-1,len(data.dates)):
            eligible,reasons=eligibility(data,main,status,config,row)
            history=History(data,main,status,row,eligible,reasons)
            scores=probe.score(history)
            ranked=probe.refine_ranking(history,scores,stable_rank(scores,eligible,data.securities))
            precise=stable_rank(sign*original[key][row],eligible,data.securities)
            assert ranked[:20].tolist()==precise[:20].tolist(),(kind,data.dates[row])
        rank_checks[kind]={'checked_days':425,'top20_equal':True}
    checked['checks']['strategy_rank_precision']=rank_checks
    reference=SimpleNamespace(values={**main.values,**original})
    signals={}
    for spec in SPECS:
        actual_strategy=StrategyRegistry().create(Config(device=device,strategy=spec.id))
        precise_strategy=StrategyRegistry().create(Config(device=device,strategy=spec.id))
        held={};decisions=0
        for row in range(data.date_index[config.start]-1,len(data.dates)):
            eligible,reasons=eligibility(data,main,status,config,row)
            actual_history=History(data,main,status,row,eligible,reasons)
            precise_history=History(data,reference,status,row,eligible,reasons)
            portfolio=SimpleNamespace(positions=held)
            actual=actual_strategy.on_close(actual_history,portfolio)
            precise=precise_strategy.on_close(precise_history,portfolio)
            assert actual.rebalance==precise.rebalance and actual.weights==precise.weights,(spec.id,data.dates[row])
            if actual.rebalance:
                held={security:{} for security in actual.weights}
                decisions+=1
        signals[spec.id]={'checked_days':425,'target_decisions':decisions,'targets_equal':True}
    checked['checks']['ten_strategy_signal_precision']=signals
    atomic_json(config.root/f"data/{device}_validation.json",checked)
    print(json.dumps(checked,ensure_ascii=False,indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--device",choices=["mps","cuda"],default="mps")
    validate(parser.parse_args().device)
