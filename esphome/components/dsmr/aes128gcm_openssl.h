#pragma once

#ifdef USE_HOST

#include <dsmr_parser/decryption/aes128gcm.h>
#include <openssl/evp.h>
#include <array>
#include <cstring>
#include <span>

namespace esphome::dsmr {

class Aes128GcmOpenSsl final : public dsmr_parser::Aes128GcmDecryptor {
 public:
  Aes128GcmOpenSsl() : ctx_(EVP_CIPHER_CTX_new()) {}
  ~Aes128GcmOpenSsl() override { EVP_CIPHER_CTX_free(this->ctx_); }
  Aes128GcmOpenSsl(const Aes128GcmOpenSsl &) = delete;
  Aes128GcmOpenSsl &operator=(const Aes128GcmOpenSsl &) = delete;
  Aes128GcmOpenSsl(Aes128GcmOpenSsl &&) = delete;
  Aes128GcmOpenSsl &operator=(Aes128GcmOpenSsl &&) = delete;

  void set_encryption_key(const dsmr_parser::Aes128GcmDecryptionKey &key) override {
    std::memcpy(this->key_.data(), key.data(), this->key_.size());
    this->initialized_ = true;
  }

  bool decrypt_inplace(std::span<const uint8_t, 12> nonce, std::span<uint8_t> ciphertext,
                       std::span<const uint8_t, 12> tag) override {
    if (!this->initialized_ || this->ctx_ == nullptr) {
      dsmr_parser::Logger::log(dsmr_parser::LogLevel::ERROR, "Decryption key is not set");
      return false;
    }

    int len = 0;
    if (EVP_DecryptInit_ex(this->ctx_, EVP_aes_128_gcm(), nullptr, nullptr, nullptr) != 1 ||
        EVP_CIPHER_CTX_ctrl(this->ctx_, EVP_CTRL_GCM_SET_IVLEN, static_cast<int>(nonce.size()), nullptr) != 1 ||
        EVP_DecryptInit_ex(this->ctx_, nullptr, nullptr, this->key_.data(), nonce.data()) != 1) {
      return false;
    }
    if (this->aad.has_value() &&
        EVP_DecryptUpdate(this->ctx_, nullptr, &len, this->aad->data(), static_cast<int>(this->aad->size())) != 1) {
      return false;
    }
    if (EVP_DecryptUpdate(this->ctx_, ciphertext.data(), &len, ciphertext.data(),
                          static_cast<int>(ciphertext.size())) != 1) {
      return false;
    }
    // No authentication key provided: decrypt without verifying the GCM tag.
    if (!this->aad.has_value()) {
      return true;
    }
    if (EVP_CIPHER_CTX_ctrl(this->ctx_, EVP_CTRL_GCM_SET_TAG, static_cast<int>(tag.size()),
                            const_cast<uint8_t *>(tag.data())) != 1) {
      return false;
    }
    uint8_t unused[16];
    return EVP_DecryptFinal_ex(this->ctx_, unused, &len) == 1;
  }

 protected:
  EVP_CIPHER_CTX *ctx_;
  std::array<uint8_t, 16> key_{};
  bool initialized_{false};
};

}  // namespace esphome::dsmr

#endif  // USE_HOST
