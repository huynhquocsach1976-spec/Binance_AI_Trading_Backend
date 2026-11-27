from unified_backtest import *
import itertools, warnings; warnings.filterwarnings("ignore")
f=feats(df)
N=len(df)
grid=list(itertools.product([8,10,12],[1.0,1.5,2.0,3.0],[2.0,3.0,4.5,6.0],["both","long","short"],[False,True],[24,10**9]))
print("combos",len(grid))
def ev(p,a,b):
    thr,slm,tpm,side,tr,mh=p
    bal,t=sim(df,f,thr,slm,tpm,side,tr,mh,risk=0,start=a,end=b); return stats(bal,t)
# rolling walk-forward: train 2000 candles (~83d), test 500 (~21d)
folds=[]; a=250
while a+2000+500<=N: folds.append((a,a+2000,a+2500)); a+=500
tot=1.0; allp=[]
for k,(s,m,e) in enumerate(folds):
    best=None
    for p in grid:
        r=ev(p,s,m)
        if r["n"]>=25 and r["pf"]<9 and (best is None or r["pf"]>best[1]["pf"]): best=(p,r)
    r=ev(best[0],m,e)
    print(f"fold{k} train PF={best[1]['pf']} ret={best[1]['ret']}%  params={best[0]} -> TEST n={r['n']} ret={r['ret']}% PF={r['pf']} dd={r['dd']}")
    tot*=1+float(r["ret"])/100; allp.append(float(r["ret"]))
print("OUT-OF-SAMPLE compounded %:",round((tot-1)*100,1), "folds:",allp)
# how many of ALL combos are profitable over full period (multiple-testing sanity)
res=[(ev(p,250,N),p) for p in grid]
prof=[x for x in res if x[0]["n"]>=40 and x[0]["ret"]>0]
print("combos profitable full-period:",len(prof),"/",len(grid))
best=sorted(res,key=lambda x:-float(x[0]["ret"]))[:5]
for r,p in best: print(p,r)
