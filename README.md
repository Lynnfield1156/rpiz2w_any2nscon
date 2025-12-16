# Raspberry Pi Zero 2 W - DS4 to Switch Bridge

DualShock 4 コントローラーを Nintendo Switch Proコントローラーとして認識させるUSBガジェットブリッジです。

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
"Waiting for DualShock 4..." と表示されたら待機状態です。

### 2. コントローラー接続
DS4のPSボタンを押して接続します。"Found DS4: ..." と表示されます。

### 3. Switch接続
Raspberry Pi の USBポート（PWRではない方）と Switch のドックをUSBケーブルで接続します。
Switchの「コントローラーの持ちかた/順番を変える」画面を開くとスムーズに認識されます。

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
| Touchpad Click | - (未割り当て) |

## トラブルシューティング
- **"gadget ... not found"**: `setup_gadget.sh` を実行し忘れています。
- **BrokenPipeError**: SwitchにUSBが繋がっていません。ケーブルを確認してください。
