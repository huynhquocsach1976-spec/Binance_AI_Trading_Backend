import pandas as pd, numpy as np, itertools
df=pd.read_csv("historical/XBTUSD_60.csv")
df["t"]=pd.to_datetime(df.timestamp,unit="s")
print(df.t.min(),df.t.max(),len(df), "gaps:",(df.timestamp.diff().dropna()!=3600).sum())
print("buy&hold %:",(df.close.iloc[-1]/df.open.iloc[0]-1)*100)
df["m"]=df.t.dt.to_period("M")
print(df.groupby("m").apply(lambda g:(g.close.iloc[-1]/g.open.iloc[0]-1)*100).round(1).to_dict())

def feats(d):
    c=d.close; o=d.open
    ema=lambda s,n:s.ewm(span=n,adjust=False).mean()
    f=pd.DataFrame(index=d.index)
    f["ema20"]=ema(c,20); f["ema50"]=ema(c,50); f["ema200"]=ema(c,200)
    dl=c.diff(); g=dl.clip(lower=0).rolling(14).mean(); l=(-dl.clip(upper=0)).rolling(14).mean()
    f["rsi"]=(100-100/(1+g/l.replace(0,np.nan))).fillna(50)
    tr=pd.concat([d.high-d.low,(d.high-c.shift()).abs(),(d.low-c.shift()).abs()],axis=1).max(axis=1)
    f["atr"]=tr.rolling(14).mean()
    m=ema(c,12)-ema(c,26); s=ema(m,9); f["macd"]=m; f["sig"]=s
    tp=(d.high+d.low+c)/3; day=d.t.dt.date
    f["vwap"]=(tp*d.volume).groupby(day).cumsum()/d.volume.groupby(day).cumsum()
    va=d.volume.rolling(20).mean(); f["vr"]=d.volume/va
    ta=d.trades.rolling(20).mean(); f["tr"]=d.trades/ta
    pH=d.high.rolling(20).max().shift(1); pL=d.low.rolling(20).min().shift(1)
    sc=np.where(f.ema20>f.ema50,2,-2)+np.where(c>f.ema20,2,-2)
    sc=sc+np.select([f.rsi>=55,f.rsi>=50,f.rsi<=35],[2,1,-2],-1)
    sc=sc+np.where(f.macd>f.sig,2,-2)+np.where(f.macd-f.sig>0,1,-1)+np.where(c>f.vwap,2,-2)
    bull=c>o; bear=c<o
    sc=sc+np.where(f.vr>=1.5,np.where(bull,2,np.where(bear,-2,0)),np.where(f.vr>=1.2,np.where(bull,1,np.where(bear,-1,0)),0))
    sc=sc+np.where(f.tr>=1.5,np.where(bull,1,np.where(bear,-1,0)),0)
    sc=sc+np.where(c>pH,3,0)-np.where(c<pL,3,0)
    f["score"]=sc; f["lowliq"]=(f.vr<0.5)|(f.tr<0.5)
    return f

def sim(d,f,thr=8,slm=1.5,tpm=3.0,side="both",trend=False,maxhold=10**9,fee=0.0004,slip=0.0001,start=250,end=None,risk=1.0):
    O=d.open.values;H=d.high.values;L=d.low.values;C=d.close.values
    sc=f.score.values;atr=f.atr.values;ll=f.lowliq.values;e200=f.ema200.values
    n=len(d) if end is None else end
    bal=1.0;tr=[];i=start
    while i<n-1:
        s=0
        if not ll[i] and np.isfinite(atr[i]):
            if sc[i]>=thr and side in("both","long"): s=1
            elif sc[i]<=-thr and side in("both","short"): s=-1
        if s and trend and ((s==1 and C[i]<e200[i]) or (s==-1 and C[i]>e200[i])): s=0
        if not s: i+=1;continue
        ep=O[i+1]*(1+slip*s); a=atr[i]
        sl=ep-s*slm*a; tp=ep+s*tpm*a; j=i+1; xp=None
        while j<n:
            if (s==1 and L[j]<=sl) or (s==-1 and H[j]>=sl): xp=sl;r="SL";break
            if (s==1 and H[j]>=tp) or (s==-1 and L[j]<=tp): xp=tp;r="TP";break
            if j-(i+1)>=maxhold: xp=C[j];r="TIME";break
            j+=1
        if xp is None: j=n-1;xp=C[j];r="EOD"
        xp=xp*(1-slip*s)
        ret=s*(xp-ep)/ep
        stop_pct=abs(ep-sl)/ep
        size=min(1.0, risk/100/stop_pct) if risk else 1.0   # risk% of equity per trade, no leverage
        pnl=size*ret-size*fee*2
        bal*=1+pnl; tr.append((s,pnl,r,i)); i=j+1
    return bal,tr
def stats(bal,tr):
    if not tr: return dict(n=0,ret=0,wr=0,pf=0)
    p=np.array([t[1] for t in tr]); g=p[p>0].sum(); l=-p[p<0].sum()
    eq=np.cumprod(1+p); dd=(1-eq/np.maximum.accumulate(eq)).max()
    return dict(n=len(p),ret=round((bal-1)*100,1),wr=round((p>0).mean()*100),pf=round(g/l,2) if l else 9.99,dd=round(dd*100,1))
