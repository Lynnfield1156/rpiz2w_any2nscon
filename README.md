# Raspberry Pi Zero 2 W - DS4 to Switch Bridge (Pro Controller Emulator)

DualShock 4 コントローラーを **純正 Nintendo Switch Proコントローラー** として完全認識させるUSBガジェットブリッジです。
SPI/UARTハンドシェイクを実装しているため、Switchからは正規のコントローラーとして認識されます。

## 特徴
- **純正Proコン互換**: ハンドシェイク（認証ごっこ）に対応し、Switchに「Pro Controller」として認識されます。
- **低遅延**: 60Hz以上のポーリングレートを維持し、入力遅延を最小限に抑えています。
- **自動再接続**: コントローラーの接続が切れても自動で再スキャンします。

## 必要要件
- Raspberry Pi Zero 2 W (または OTG対応のラズパイ)
- DualShock 4 コントローラー
- microUSBケーブル (データ通信対応) -> Switch接続用

## インストールとセットアップ（初回のみ）

### 1. USBガジェットの設定
```bash
cd ~/rpiz2w_any2nscon
sudo ./setup_gadget.sh
```

### 2. Bluetoothペアリング
```bash
sudo bluetoothctl
```
`bluetoothctl` 内で以下を実行:
```
agent on
default-agent
power on
scan on
```
DS4をペアリングモード（SHARE + PS長押し）にして、見つかったら:
```
pair <MAC address>
connect <MAC address>
trust <MAC address>
```

## 使い方

### 1. 実行
```bash
sudo python3 bridge_controller.py
```
"Waiting for DS4..." と表示されたら待機状態です。

### 2. コントローラー接続
DS4のPSボタンを押して接続します。"Found DS4: ..." と表示されます。

### 3. Switch接続
Raspberry Pi の USBポート（PWRではない方）と Switch のドックをUSBケーブルで接続します。
Switchの「コントローラーの持ちかた/順番を変える」画面を開くと、数秒で認識されます。

## ボタン対応表
| DS4 | Switch |
|---|---|
| × | B |
| ○ | A |
| □ | Y |
| △ | X |
| L1/R1 | L/R |
| L2/R2 | ZL/ZR |
| SHARE | - (Minus) |
| OPTIONS | + (Plus) |
| PS | HOME |
| L3/R3 | LStick/RStick Click |

## クレジット & 参考
本プロジェクトは以下の偉大な先人たちの成果を参考に実装されています：
- [mizuyoukanao/NXIC](https://github.com/mizuyoukanao/NXIC)
- [mzyy94: スマホでNintendo Switchを操作する](https://www.mzyy94.com/blog/2020/03/20/nintendo-switch-pro-controller-usb-gadget/)
- [Bokuchin: マウスを任天堂スイッチのプロコンのジャイロに連動させる](https://qiita.com/Bokuchin/items/7fee2c6a04c97dde29b4)

## トラブルシューティング
- **"gadget ... not found"**: `setup_gadget.sh` を実行し忘れています。
- **BrokenPipeError**: SwitchにUSBが繋がっていません。ケーブルを確認してください。
