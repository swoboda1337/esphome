#include <gtest/gtest.h>

#include <cstdint>

#include "esphome/core/helpers.h"

namespace esphome::core::testing {

TEST(ParseNumber, UnsignedAcceptsDecimal) {
  EXPECT_EQ(parse_number<uint8_t>("255"), 255);
  EXPECT_EQ(parse_number<uint32_t>("0"), 0u);
  EXPECT_EQ(parse_number<uint32_t>("4294967295"), UINT32_MAX);
  EXPECT_EQ(parse_number<uint64_t>("18446744073709551615"), UINT64_MAX);
}

TEST(ParseNumber, UnsignedRejectsNegative) {
  EXPECT_FALSE(parse_number<uint8_t>("-1").has_value());
  EXPECT_FALSE(parse_number<uint32_t>("-1").has_value());
  EXPECT_FALSE(parse_number<uint64_t>("-1").has_value());
  EXPECT_FALSE(parse_number<uint64_t>("-0").has_value());
}

TEST(ParseNumber, UnsignedRejectsOutOfRange) {
  EXPECT_FALSE(parse_number<uint8_t>("256").has_value());
  EXPECT_FALSE(parse_number<uint32_t>("4294967296").has_value());
  EXPECT_FALSE(parse_number<uint64_t>("18446744073709551616").has_value());
}

TEST(ParseNumber, SignedAcceptsDecimal) {
  EXPECT_EQ(parse_number<int8_t>("-128"), -128);
  EXPECT_EQ(parse_number<int32_t>("-2147483648"), INT32_MIN);
  EXPECT_EQ(parse_number<int64_t>("9223372036854775807"), INT64_MAX);
  EXPECT_EQ(parse_number<int64_t>("-9223372036854775808"), INT64_MIN);
}

TEST(ParseNumber, SignedRejectsOutOfRange) {
  EXPECT_FALSE(parse_number<int8_t>("128").has_value());
  EXPECT_FALSE(parse_number<int32_t>("2147483648").has_value());
  EXPECT_FALSE(parse_number<int64_t>("9223372036854775808").has_value());
  EXPECT_FALSE(parse_number<int64_t>("-9223372036854775809").has_value());
}

TEST(ParseNumber, RejectsMalformed) {
  EXPECT_FALSE(parse_number<uint32_t>("").has_value());
  EXPECT_FALSE(parse_number<uint32_t>("12a").has_value());
  EXPECT_FALSE(parse_number<int32_t>("-").has_value());
}

}  // namespace esphome::core::testing
