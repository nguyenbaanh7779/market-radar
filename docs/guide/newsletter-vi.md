# Cách đọc bản tin Market Radar

Bản tin đến qua Telegram mỗi sáng ngày giao dịch (khoảng 05:30–06:30). Nó tóm tắt phiên
giao dịch gần nhất và đưa ra nhận định cho phiên sắp tới. Mỗi câu nói **ý nghĩa trước**,
**con số thật để trong ngoặc**.

> Đây là sản phẩm nghiên cứu cho đồ án, **không phải khuyến nghị đầu tư**. Mô hình hiện mới
> nhỉnh hơn đoán ngẫu nhiên một chút (xem mục 9).

## 1. Tiêu đề

`MARKET RADAR · phiên 17/11/2026 · nhận định cho phiên 18/11/2026`

- **Phiên 17/11:** dữ liệu đóng cửa mới nhất mà bản tin dùng.
- **Nhận định cho phiên 18/11:** phiên mà dự báo và lệnh mô phỏng hướng tới.

## 2. 📌 Tóm tắt

Hai đến ba câu, đủ để nắm tình hình khi chỉ có một phút:

1. **Thị trường khoẻ hay yếu.** "Đang yếu" khi VNINDEX ở xu hướng giảm, hoặc dưới 40%
   cổ phiếu tăng giá. "Đang khoẻ" khi VNINDEX ở xu hướng tăng và từ 50% cổ phiếu trở lên
   tăng giá. Các trường hợp còn lại là "chưa rõ xu hướng".
2. **Tiền đang chảy vào hay rút khỏi ngành nào** (xem mục 5).
3. **Mô hình có tín hiệu rõ cho VNINDEX phiên tới hay không** (xem mục 4).

## 3. Thị trường

| Dòng | Ý nghĩa |
|---|---|
| **Xu hướng** | So giá VNINDEX với **mức trung bình 20 phiên** (khoảng 1 tháng) và **50 phiên** (khoảng 2,5 tháng). Giá trên cả hai là xu hướng **tăng**, dưới cả hai là **giảm**, còn lại là **đi ngang**. Số trong ngoặc là giá đang cao hoặc thấp hơn mức trung bình bao nhiêu %. |
| **Dao động** | Thị trường lên xuống mạnh hay nhẹ. Số `%/năm` là mức dao động quy ra một năm (khoảng 15–20% là bình thường với VNINDEX). "Cao hơn 54% số phiên trong 1 năm qua" nghĩa là hôm nay dao động hơn một nửa số ngày của năm qua: thấp (< 30%), bình thường (30–70%), cao (70–90%), rất cao (> 90%). |
| **Độ lan toả** | Bao nhiêu cổ phiếu cùng tăng. Chỉ số có thể tăng nhờ vài mã lớn trong khi đa số giảm; độ lan toả cho biết điều đó. Yếu (< 40% mã tăng), trung bình (40–60%), tốt (> 60%). "% còn trên trung bình 20 phiên" cho biết bao nhiêu mã vẫn giữ được xu hướng ngắn hạn. |
| **Thanh khoản** | Giá trị giao dịch so với trung bình 20 phiên. Chỉ hiện khi nguồn dữ liệu có khối lượng (nguồn Arena hiện chưa có). |

## 4. Dự báo chỉ số

`VNINDEX · Phiên tới: gần như ngang nhau (tăng 46% · đi ngang 21% · giảm 33%)`

- Ba con số là **xác suất** phiên tới (hoặc 5 phiên tới) sẽ:
  - **tăng** hơn 0,2%;
  - **đi ngang** trong khoảng ±0,2%;
  - **giảm** hơn 0,2%.

  Tổng ba số là 100%.
- **Độ chắc chắn** dựa trên xác suất cao nhất:
  - dưới 55%: **gần như ngang nhau**, tức không nên dựa vào;
  - 55–65%: **hơi nghiêng** về một phía;
  - trên 65%: **nghiêng rõ**.
- **BANKS** là rổ chia đều tỷ trọng của 20 ngân hàng niêm yết, đại diện cho nhóm ngân hàng.

## 5. Ngành mạnh nhất / yếu nhất

Mỗi ngành là một rổ cổ phiếu đại diện, được so với VNINDEX bằng hai số:

- **Sức mạnh:** trên 100 là ngành đang mạnh hơn thị trường so với mức thường thấy của nó;
  dưới 100 là yếu hơn.
- **Động lượng:** trên 100 là sức mạnh đó đang tăng lên; dưới 100 là đang giảm đi.

Kết hợp hai số cho ra bốn trạng thái:

| Trạng thái | Sức mạnh | Động lượng | Diễn giải |
|---|---|---|---|
| Mạnh hơn thị trường và đang tăng tốc | > 100 | > 100 | Ngành dẫn dắt, đang hút tiền |
| Vẫn mạnh hơn nhưng đang chậm lại | > 100 | < 100 | Có thể sắp hết sức |
| Yếu hơn, chưa có dấu hiệu hồi phục | < 100 | < 100 | Đang bị rút tiền |
| Còn yếu hơn nhưng đang hồi phục | < 100 | > 100 | Có thể sắp mạnh lên |

## 6. Mã đáng chú ý và cần cảnh giác

```
1. PNJ — khả năng tăng 56% (hơi nghiêng về tăng)
   Vì sao: xu hướng trung hạn đi xuống (MA20 thấp hơn MA50 31,3%); giảm gần đây
   (-27,1% trong 20 phiên) → mô hình kỳ vọng hồi phục sau đợt giảm
```

- **Khả năng tăng/giảm:** xác suất mô hình dự báo cho **5 phiên tới**, kèm độ chắc chắn
  như ở mục 4.
- **Vì sao:** hai yếu tố tác động mạnh nhất tới dự báo, kèm số liệu thật của mã đó.
- **"→ mô hình kỳ vọng hồi phục sau đợt giảm":** mô hình dự báo tăng chính *vì* mã đã
  giảm mạnh. Đây là cược vào việc giá đảo chiều, rủi ro hơn so với đi theo xu hướng.
- **Tín hiệu kỹ thuật** (chỉ hiện khi không phải "trung tính") là luật cố định, độc lập
  với mô hình:
  - **mạnh:** giá trên MA20, MA20 trên MA50, MACD dương, RSI từ 50 đến 70;
  - **cảnh giác:** RSI ≥ 75 (quá mua), hoặc giá dưới MA50 kèm MACD âm, hoặc giá thủng dải
    Bollinger dưới.

## 7. Danh mục của bạn

Chỉ hiện khi bạn khai báo danh mục, và chỉ có trong tin Telegram, không có trong bản lưu
trên GitHub.

- **Giá trị** và **lãi/lỗ** so với giá vốn.
- **So sánh với VN30** cùng kỳ.
- **Mức tập trung** (HHI): từ 0,25 trở lên là danh mục dồn vào ít mã.
- Các mã đang có tín hiệu yếu, hoặc thuộc ngành đang bị rút tiền.

## 8. Giao dịch mô phỏng

Một **tài khoản ảo 100 triệu đồng** làm theo dự báo, để kiểm chứng xem dự báo có
kiếm được tiền hay không. Đây là câu hỏi nghiên cứu RQ4.

- Mỗi 5 phiên, tài khoản chọn tối đa 5 mã có khả năng tăng cao nhất. Mỗi mã chiếm tối đa
  30% vốn; phần còn lại để tiền mặt.
- Lệnh được **khớp ở giá đóng cửa** của phiên ghi trong bản tin.
- Mua theo lô 100 cổ phiếu. Cổ phiếu về tài khoản sau **T+2**, mới bán được. Phí 0,15% mỗi
  chiều, thuế bán 0,1%.
- Tự **cắt lỗ** khi giá giảm 7% so với giá vốn.
- "**lưu ý: tín hiệu kỹ thuật cảnh giác**": mô hình vẫn chọn mua dù luật kỹ thuật đang
  cảnh báo, vì hiện chiến lược chỉ dựa vào xác suất của mô hình.

## 9. Giới hạn cần nhớ

- Mô hình hiện mới **nhỉnh hơn baseline một chút** ở dự báo 1 phiên cho cổ phiếu, và
  **chưa** hơn baseline ở dự báo 5 phiên hay dự báo chỉ số.
- Trong backtest 2024–2026, chiến lược mô phỏng **thua** VN30 mua và giữ.
- Bản tin phục vụ nghiên cứu. Đừng dùng nó làm căn cứ duy nhất cho quyết định đầu tư.

## 10. Thuật ngữ

| Thuật ngữ | Giải thích ngắn |
|---|---|
| Trung bình 20/50 phiên (MA20, MA50) | Giá đóng cửa trung bình của 20 hoặc 50 phiên gần nhất, dùng để nhìn xu hướng ngắn và trung hạn |
| RSI | Chỉ báo 0–100 đo lực mua so với lực bán trong 14 phiên. ≥ 70 là quá mua, ≤ 30 là quá bán |
| MACD | Hiệu giữa hai đường trung bình nhanh và chậm. Dương nghĩa là đà tăng ngắn hạn |
| Dải Bollinger | Vùng quanh MA20 rộng ±2 độ lệch chuẩn. Giá vượt ra ngoài dải là biến động bất thường |
| Phiên | Một ngày giao dịch (không tính cuối tuần và ngày lễ) |
| T+2 | Cổ phiếu mua hôm nay về tài khoản sau 2 phiên mới bán được |
| Lô 100 | Mua bán theo bội số của 100 cổ phiếu |
