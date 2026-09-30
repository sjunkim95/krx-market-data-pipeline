# 필요한 패키지 설치
# install.packages(c("DBI", "RPostgres"))
# install.packages("dotenv")

# PostgreSQL 연결 및 데이터 분석에 사용할 패키지 로드
library(DBI)
library(RPostgres)
library(dplyr)
library(ggplot2)
library(dotenv)

# .env 파일에서 DB 접속 정보 불러오기
load_dot_env("../.env")

# PostgreSQL 데이터베이스 연결
con <- dbConnect(
  RPostgres::Postgres(),
  host = Sys.getenv("PGHOST"),
  port = as.integer(Sys.getenv("PGPORT")),
  dbname = Sys.getenv("PGDATABASE"),
  user = Sys.getenv("PGUSER"),
  password = Sys.getenv("PGPASSWORD")
)

# DB 연결 및 테이블 확인
dbListTables(con)

# 데이터 일부를 먼저 조회해 구조 확인
dbGetQuery(con, "SELECT * FROM kospi_daily_prices LIMIT 5")

# KOSPI 일별 시세 전체 데이터를 R로 불러오기
krx <- dbGetQuery(
  con,
  "SELECT * FROM kospi_daily_prices"
)

# 데이터 기본 구조와 범위 확인
head(krx)
str(krx)
class(krx$trade_date)
nrow(krx)
summary(krx$change_rate)

# 등락률이 가장 낮은 10개 기록 확인
krx %>%
  arrange(change_rate) %>%
  select(trade_date, stock_name, change_rate) %>%
  head(10)

# 등락률이 가장 높은 10개 기록 확인
krx %>%
  arrange(desc(change_rate)) %>%
  select(trade_date, stock_name, change_rate) %>%
  head(10)

# ggplot에서 사용하기 쉽도록 거래대금을 일반 numeric으로 변환
krx <- krx %>%
  mutate(trading_value_num = as.numeric(trading_value))

# 거래대금과 등락률의 전체적인 관계를 산점도로 확인
ggplot(
  krx %>%
    filter(trading_value_num > 0),
  aes(x = trading_value_num, y = change_rate)
) +
  geom_point(alpha = 0.2) +
  scale_x_log10() +
  labs(
    title = "Trading Value vs Change Rate",
    x = "Trading Value (Log Scale)",
    y = "Change Rate (%)"
  ) +
  theme_minimal()

# 원본 거래대금과 등락률 사이의 선형 관계 확인
cor(
  krx$trading_value_num,
  krx$change_rate,
  use = "complete.obs"
)

# 거래대금 0인 행은 제외하고, 로그 거래대금 컬럼을 새로 생성
krx_log <- krx %>%
  filter(trading_value_num > 0) %>%
  mutate(log_trading_value = log10(trading_value_num))

# 로그 거래대금과 등락률 사이의 선형 관계 확인
cor(
  krx_log$log_trading_value,
  krx_log$change_rate,
  use = "complete.obs"
)

# 중앙값이 0인 종목은 제외하고 거래대금 급증 비율 계산
volume_spike_median <- krx %>%
  group_by(ticker, stock_name) %>%
  mutate(
    median_trading_value = median(trading_value_num, na.rm = TRUE)
  ) %>%
  ungroup() %>%
  filter(median_trading_value > 0) %>%
  mutate(
    trading_value_ratio_median =
      trading_value_num / median_trading_value
  )

# 중앙값 대비 거래대금 급증 Top 10 확인
volume_spike_median %>%
  arrange(desc(trading_value_ratio_median)) %>%
  select(
    trade_date,
    stock_name,
    trading_value_num,
    median_trading_value,
    trading_value_ratio_median,
    change_rate
  ) %>%
  head(10)

# 주가 등락의 방향이 아니라 변동 크기를 보기 위해 절대 등락률 생성
volume_spike_median <- volume_spike_median %>%
  mutate(abs_change_rate = abs(change_rate))

# 거래대금 급증 비율과 절대 등락률의 선형 관계 확인
cor(
  volume_spike_median$trading_value_ratio_median,
  volume_spike_median$abs_change_rate,
  use = "complete.obs"
)

# 거래대금 급증 비율과 절대 등락률 관계 시각화
ggplot(
  volume_spike_median %>%
    filter(trading_value_ratio_median > 0),
  aes(x = trading_value_ratio_median, y = abs_change_rate)
) +
  geom_point(alpha = 0.2) +
  scale_x_log10() +
  labs(
    title = "Trading Value Spike vs Absolute Change Rate",
    x = "Trading Value Ratio (Log Scale)",
    y = "Absolute Change Rate (%)"
  ) +
  theme_minimal()

# 특수값 제외 후 거래대금 급증 구간 생성
normal_move <- volume_spike_median %>%
  filter(abs_change_rate <= 30) %>%
  mutate(
    spike_level = case_when(
      trading_value_ratio_median < 1 ~ "Below 1x",
      trading_value_ratio_median < 2 ~ "1x-2x",
      trading_value_ratio_median < 5 ~ "2x-5x",
      trading_value_ratio_median < 10 ~ "5x-10x",
      TRUE ~ "10x+"
    ),
    spike_level = factor(
      spike_level,
      levels = c("Below 1x", "1x-2x", "2x-5x", "5x-10x", "10x+")
    )
  )

# 특수값 제외 후 거래대금 급증 비율과 절대 등락률의 상관관계 확인
cor(
  normal_move$trading_value_ratio_median,
  normal_move$abs_change_rate,
  use = "complete.obs"
)

# 거래대금 급증 구간별 평균 절대 등락률 비교
spike_group <- normal_move %>%
  group_by(spike_level) %>%
  summarise(
    avg_abs_change_rate = mean(abs_change_rate, na.rm = TRUE),
    count = n()
  )

spike_group

# 거래대금 급증 구간별 평균 절대 등락률 시각화
ggplot(
  spike_group,
  aes(x = spike_level, y = avg_abs_change_rate)
) +
  geom_col() +
  geom_text(
    aes(label = paste0(round(avg_abs_change_rate, 2), "%")),
    vjust = -0.3
  ) +
  labs(
    title = "Average Absolute Change Rate by Trading Value Spike",
    x = "Trading Value Spike Level",
    y = "Average Absolute Change Rate (%)"
  ) +
  theme_minimal()

# 거래대금 급증 구간별 5% 이상 변동 발생 비율 계산
large_move_group <- normal_move %>%
  mutate(
    large_move = abs_change_rate >= 5
  ) %>%
  group_by(spike_level) %>%
  summarise(
    large_move_rate = mean(large_move, na.rm = TRUE) * 100,
    count = n()
  )

large_move_group

# 거래대금 급증 구간별 5% 이상 변동 발생 비율 시각화
ggplot(
  large_move_group,
  aes(x = spike_level, y = large_move_rate)
) +
  geom_col() +
  geom_text(
    aes(label = paste0(round(large_move_rate, 1), "%")),
    vjust = -0.3
  ) +
  scale_y_continuous(
    limits = c(0, 100),
    breaks = seq(0, 100, 10)
  ) +
  labs(
    title = "Frequency of 5%+ Price Moves by Trading Value Spike",
    x = "Trading Value Spike Level",
    y = "5%+ Move Rate (%)"
  ) +
  theme_minimal()

# 거래대금 급증 구간별 상승/하락/보합 비율 계산
direction_share <- normal_move %>%
  mutate(
    direction = case_when(
      is.na(change_rate) ~ NA_character_,
      change_rate > 0 ~ "Up",
      change_rate < 0 ~ "Down",
      TRUE ~ "Flat"
    )
  ) %>%
  count(spike_level, direction) %>%
  filter(!is.na(direction)) %>%
  group_by(spike_level) %>%
  mutate(
    rate = n / sum(n) * 100
  ) %>%
  ungroup()

direction_share

# 거래대금 급증 구간별 상승/하락/보합 비율 시각화
ggplot(
  direction_share,
  aes(x = spike_level, y = rate, fill = direction)
) +
  geom_col() +
  scale_y_continuous(
    limits = c(0, 100),
    breaks = seq(0, 100, 10)
  ) +
  scale_fill_manual(
    values = c(
      "Up" = "red",
      "Down" = "blue",
      "Flat" = "gray"
    )
  ) +
  labs(
    title = "Price Direction by Trading Value Spike",
    x = "Trading Value Spike Level",
    y = "Price Direction Share (%)",
    fill = "Direction"
  ) +
  theme_minimal()

# PostgreSQL 연결 종료
dbDisconnect(con)

# README에 사용할 그래프 저장 폴더 생성
dir.create("../images", showWarnings = FALSE)

# 1. 거래대금과 등락률 관계
p1 <- ggplot(
  krx %>%
    filter(trading_value_num > 0),
  aes(x = trading_value_num, y = change_rate)
) +
  geom_point(alpha = 0.2) +
  scale_x_log10() +
  labs(
    title = "Trading Value vs Change Rate",
    x = "Trading Value (Log Scale)",
    y = "Change Rate (%)"
  ) +
  theme_minimal()


# 2. 거래대금 급증 비율과 절대 등락률 관계
p2 <- ggplot(
  volume_spike_median %>%
    filter(trading_value_ratio_median > 0),
  aes(x = trading_value_ratio_median, y = abs_change_rate)
) +
  geom_point(alpha = 0.2) +
  scale_x_log10() +
  labs(
    title = "Trading Value Spike vs Absolute Change Rate",
    x = "Trading Value Ratio (Log Scale)",
    y = "Absolute Change Rate (%)"
  ) +
  theme_minimal()


# 3. 거래대금 급증 구간별 평균 절대 등락률
p3 <- ggplot(
  spike_group,
  aes(x = spike_level, y = avg_abs_change_rate)
) +
  geom_col() +
  geom_text(
    aes(label = paste0(round(avg_abs_change_rate, 2), "%")),
    vjust = -0.3
  ) +
  labs(
    title = "Average Absolute Change Rate by Trading Value Spike",
    x = "Trading Value Spike Level",
    y = "Average Absolute Change Rate (%)"
  ) +
  theme_minimal()


# 4. 거래대금 급증 구간별 5% 이상 변동 발생 비율
p4 <- ggplot(
  large_move_group,
  aes(x = spike_level, y = large_move_rate)
) +
  geom_col() +
  geom_text(
    aes(label = paste0(round(large_move_rate, 1), "%")),
    vjust = -0.3
  ) +
  scale_y_continuous(
    limits = c(0, 100),
    breaks = seq(0, 100, 10)
  ) +
  labs(
    title = "Frequency of 5%+ Price Moves by Trading Value Spike",
    x = "Trading Value Spike Level",
    y = "5%+ Move Rate (%)"
  ) +
  theme_minimal()


# 5. 거래대금 급증 구간별 상승/하락/보합 비율
p5 <- ggplot(
  direction_share,
  aes(x = spike_level, y = rate, fill = direction)
) +
  geom_col() +
  scale_y_continuous(
    limits = c(0, 100),
    breaks = seq(0, 100, 10)
  ) +
  scale_fill_manual(
    values = c(
      "Up" = "red",
      "Down" = "blue",
      "Flat" = "gray"
    )
  ) +
  labs(
    title = "Price Direction by Trading Value Spike",
    x = "Trading Value Spike Level",
    y = "Price Direction Share (%)",
    fill = "Direction"
  ) +
  theme_minimal()

# README용 그래프 PNG 저장
ggsave(
  "../images/trading_value_vs_change_rate.png",
  plot = p1,
  width = 8,
  height = 5,
  dpi = 300,
  bg = "white"
)

ggsave(
  "../images/trading_value_spike_vs_abs_change.png",
  plot = p2,
  width = 8,
  height = 5,
  dpi = 300,
  bg = "white"
)

ggsave(
  "../images/avg_abs_change_by_spike.png",
  plot = p3,
  width = 8,
  height = 5,
  dpi = 300,
  bg = "white"
)

ggsave(
  "../images/five_percent_move_frequency.png",
  plot = p4,
  width = 8,
  height = 5,
  dpi = 300,
  bg = "white"
)

ggsave(
  "../images/price_direction_by_spike.png",
  plot = p5,
  width = 8,
  height = 5,
  dpi = 300,
  bg = "white"
)