# Hyperliquid 持仓量(OI) 5分钟变化监控

不依赖 Coinglass 付费 API，直接用 Hyperliquid 官方免费公开接口
(`https://api.hyperliquid.xyz/info`)拉全市场持仓量数据，每5分钟和上一次快照比较，
变化超过设定阈值（默认10%）就用 Bark 推送提醒到你手机。

## 部署步骤（全程免费，用 GitHub Actions 定时跑）

1. **准备 Bark**
   - iOS 上安装 Bark App，打开后会看到一个类似
     `https://api.day.app/你的KEY/` 的推送地址，记下这个 `KEY`。

2. **建一个 GitHub 仓库**
   - 新建一个仓库（Public/Private 都行），把本目录下这几个文件传上去：
     - `monitor.py`
     - `requirements.txt`
     - `state.json`
     - `.github/workflows/monitor.yml` ← 注意 `monitor.yml` 要放进
       `.github/workflows/` 这个路径下（新建文件时直接输入完整路径
       `.github/workflows/monitor.yml` 即可，GitHub 会自动建好文件夹）。

3. **配置 Bark Key**
   - 仓库页面 → Settings → Secrets and variables → Actions → New repository secret
   - Name 填 `BARK_KEY`，Value 填你第1步拿到的 KEY。

4. **打开 Actions**
   - 仓库页面 → Actions 标签 → 如果提示 enable，点一下启用。
   - 默认每5分钟自动跑一次；也可以在 Actions 页面手动点
     "Run workflow" 立即测试一次。

完成后就会在后台持续监控，符合条件时手机会收到 Bark 推送。

## 想只监控自己的持仓币种，而不是全市场？

打开 `.github/workflows/monitor.yml`，把这一行取消注释并改成你要的币种：

```yaml
OI_WATCHLIST: "B2,MMT,STRK,AR,MARSCOIN,ARK,VTHO,USELESS"
```

## 参数说明

在 `monitor.yml` 里可以调的环境变量：

| 变量 | 说明 | 默认值 |
|---|---|---|
| `OI_CHANGE_THRESHOLD` | 触发提醒的变化百分比 | `10` |
| `OI_WATCHLIST` | 只看这些币，逗号分隔；留空=全市场 | 空(全市场) |
| `MAX_SNAPSHOT_AGE_SECONDS` | 超过这么久没跑的旧快照不拿来比较，防止误报 | `900`（15分钟） |

## 已知限制

- GitHub Actions 的 `schedule` 定时任务在系统繁忙时可能延迟几分钟才触发，
  不是精确到秒的5分钟，遇到这种情况脚本会用实际的时间间隔换算百分比，
  超过 `MAX_SNAPSHOT_AGE_SECONDS` 的旧数据会被丢弃、不做比较。
- Hyperliquid 接口返回的是全市场"永续合约"持仓量，不含 Coinglass 里
  聚合多个中心化交易所(Binance/OKX/Bybit等)的那部分数据，两者数字不直接对应，
  但截图里那些币(B2/MMT/STRK/AR/MARSCOIN/ARK/VTHO/USELESS等)本身就是
  Hyperliquid 上的永续合约，用这个接口的数据是最贴近的。
