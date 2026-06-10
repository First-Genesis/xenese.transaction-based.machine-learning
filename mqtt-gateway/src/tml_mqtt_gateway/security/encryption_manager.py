"""
Encryption Manager
End-to-end message payload encryption for sensitive IoT data
"""

import base64
import json
import os
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
from cryptography.fernet import Fernet
import structlog

from ..config import TMLGatewayConfig


logger = structlog.get_logger(__name__)


class EncryptionMethod:
    """Supported encryption methods"""

    AES_256_GCM = "aes_256_gcm"
    AES_256_CBC = "aes_256_cbc"
    FERNET = "fernet"
    RSA_OAEP = "rsa_oaep"


class EncryptionManager:
    """
    Message Payload Encryption System

    Features:
    - Multiple encryption algorithms
    - Key rotation and management
    - Per-device encryption keys
    - Hybrid encryption (RSA + AES)
    - Message integrity verification
    - Performance optimization
    """

    def __init__(self, config: TMLGatewayConfig):
        self.config = config

        # Encryption configuration
        self.default_method = EncryptionMethod.AES_256_GCM
        self.key_rotation_days = 90

        # Master key for key derivation (in production, use KMS)
        self.master_key = os.environ.get(
            "TML_MASTER_KEY", "default_master_key_change_in_production"
        )

        # Device encryption keys cache
        self.device_keys = {}  # device_id -> encryption_key
        self.key_metadata = {}  # device_id -> key_metadata

        # RSA key pairs for hybrid encryption
        self.rsa_keys = {}  # device_id -> (private_key, public_key)

        self.logger = logger.bind(component="encryption_manager")

    def initialize(self) -> None:
        """Initialize encryption manager"""
        self.logger.info(
            "Encryption manager initialized",
            default_method=self.default_method,
            key_rotation_days=self.key_rotation_days,
        )

    def generate_device_key(self, device_id: str, method: str = None) -> bytes:
        """
        Generate encryption key for device

        Args:
            device_id: Device identifier
            method: Encryption method to use

        Returns:
            Encryption key bytes
        """
        method = method or self.default_method

        try:
            # Derive key from master key and device ID
            kdf = PBKDF2(
                algorithm=hashes.SHA256(),
                length=32,  # 256 bits
                salt=device_id.encode("utf-8"),
                iterations=100000,
            )

            key = kdf.derive(self.master_key.encode("utf-8"))

            # Cache key
            self.device_keys[device_id] = key
            self.key_metadata[device_id] = {
                "method": method,
                "created_at": datetime.utcnow(),
                "rotation_due": datetime.utcnow()
                + timedelta(days=self.key_rotation_days),
            }

            self.logger.info(
                "Generated device encryption key", device_id=device_id, method=method
            )

            return key

        except Exception as e:
            self.logger.error(
                "Failed to generate device key", device_id=device_id, error=str(e)
            )
            raise

    def encrypt_message(
        self, device_id: str, message: Dict[str, Any], method: str = None
    ) -> Dict[str, Any]:
        """
        Encrypt message payload

        Args:
            device_id: Device identifier
            message: Message to encrypt
            method: Encryption method

        Returns:
            Encrypted message with metadata
        """
        method = method or self.default_method

        try:
            # Get or generate device key
            if device_id not in self.device_keys:
                self.generate_device_key(device_id, method)

            key = self.device_keys[device_id]

            # Serialize message
            plaintext = json.dumps(message).encode("utf-8")

            # Encrypt based on method
            if method == EncryptionMethod.AES_256_GCM:
                ciphertext, nonce, tag = self._encrypt_aes_gcm(plaintext, key)

                encrypted_message = {
                    "_encrypted": True,
                    "_encryption_method": method,
                    "_device_id": device_id,
                    "_timestamp": datetime.utcnow().isoformat(),
                    "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
                    "nonce": base64.b64encode(nonce).decode("utf-8"),
                    "tag": base64.b64encode(tag).decode("utf-8"),
                }

            elif method == EncryptionMethod.FERNET:
                ciphertext = self._encrypt_fernet(plaintext, key)

                encrypted_message = {
                    "_encrypted": True,
                    "_encryption_method": method,
                    "_device_id": device_id,
                    "_timestamp": datetime.utcnow().isoformat(),
                    "ciphertext": ciphertext.decode("utf-8"),
                }

            else:
                raise ValueError(f"Unsupported encryption method: {method}")

            return encrypted_message

        except Exception as e:
            self.logger.error(
                "Failed to encrypt message", device_id=device_id, error=str(e)
            )
            raise

    def decrypt_message(self, encrypted_message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt message payload

        Args:
            encrypted_message: Encrypted message with metadata

        Returns:
            Decrypted message
        """
        try:
            # Check if message is encrypted
            if not encrypted_message.get("_encrypted"):
                return encrypted_message

            device_id = encrypted_message["_device_id"]
            method = encrypted_message["_encryption_method"]

            # Get device key
            if device_id not in self.device_keys:
                raise ValueError(f"No encryption key for device: {device_id}")

            key = self.device_keys[device_id]

            # Decrypt based on method
            if method == EncryptionMethod.AES_256_GCM:
                ciphertext = base64.b64decode(encrypted_message["ciphertext"])
                nonce = base64.b64decode(encrypted_message["nonce"])
                tag = base64.b64decode(encrypted_message["tag"])

                plaintext = self._decrypt_aes_gcm(ciphertext, key, nonce, tag)

            elif method == EncryptionMethod.FERNET:
                ciphertext = encrypted_message["ciphertext"].encode("utf-8")
                plaintext = self._decrypt_fernet(ciphertext, key)

            else:
                raise ValueError(f"Unsupported encryption method: {method}")

            # Parse decrypted message
            message = json.loads(plaintext.decode("utf-8"))

            return message

        except Exception as e:
            self.logger.error("Failed to decrypt message", error=str(e))
            raise

    def _encrypt_aes_gcm(
        self, plaintext: bytes, key: bytes
    ) -> Tuple[bytes, bytes, bytes]:
        """
        Encrypt using AES-256-GCM

        Returns:
            Tuple of (ciphertext, nonce, tag)
        """
        # Generate random nonce
        nonce = os.urandom(12)  # 96 bits for GCM

        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(nonce),
        )

        encryptor = cipher.encryptor()

        # Encrypt
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()

        return ciphertext, nonce, encryptor.tag

    def _decrypt_aes_gcm(
        self, ciphertext: bytes, key: bytes, nonce: bytes, tag: bytes
    ) -> bytes:
        """Decrypt using AES-256-GCM"""
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(nonce, tag),
        )

        decryptor = cipher.decryptor()

        # Decrypt
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        return plaintext

    def _encrypt_fernet(self, plaintext: bytes, key: bytes) -> bytes:
        """Encrypt using Fernet (symmetric encryption)"""
        # Fernet requires 32 bytes key encoded as base64
        fernet_key = base64.urlsafe_b64encode(key[:32])
        f = Fernet(fernet_key)

        return f.encrypt(plaintext)

    def _decrypt_fernet(self, ciphertext: bytes, key: bytes) -> bytes:
        """Decrypt using Fernet"""
        fernet_key = base64.urlsafe_b64encode(key[:32])
        f = Fernet(fernet_key)

        return f.decrypt(ciphertext)

    def generate_rsa_keypair(
        self, device_id: str, key_size: int = 2048
    ) -> Tuple[bytes, bytes]:
        """
        Generate RSA key pair for device (for hybrid encryption)

        Returns:
            Tuple of (private_key_pem, public_key_pem)
        """
        try:
            # Generate key pair
            private_key = rsa.generate_private_key(
                public_exponent=65537, key_size=key_size
            )

            public_key = private_key.public_key()

            # Convert to PEM format
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )

            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )

            # Cache keys
            self.rsa_keys[device_id] = (private_key, public_key)

            self.logger.info(
                "Generated RSA key pair", device_id=device_id, key_size=key_size
            )

            return private_pem, public_pem

        except Exception as e:
            self.logger.error(
                "Failed to generate RSA key pair", device_id=device_id, error=str(e)
            )
            raise

    def encrypt_with_public_key(
        self, device_id: str, plaintext: bytes, public_key_pem: bytes = None
    ) -> bytes:
        """
        Encrypt data using device's RSA public key

        Args:
            device_id: Device identifier
            plaintext: Data to encrypt
            public_key_pem: Public key (if not cached)

        Returns:
            Encrypted data
        """
        try:
            # Get public key
            if public_key_pem:
                public_key = serialization.load_pem_public_key(public_key_pem)
            elif device_id in self.rsa_keys:
                _, public_key = self.rsa_keys[device_id]
            else:
                raise ValueError(f"No RSA key for device: {device_id}")

            # Encrypt with OAEP padding
            ciphertext = public_key.encrypt(
                plaintext,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )

            return ciphertext

        except Exception as e:
            self.logger.error(
                "Failed to encrypt with public key", device_id=device_id, error=str(e)
            )
            raise

    def decrypt_with_private_key(
        self, device_id: str, ciphertext: bytes, private_key_pem: bytes = None
    ) -> bytes:
        """
        Decrypt data using device's RSA private key

        Args:
            device_id: Device identifier
            ciphertext: Encrypted data
            private_key_pem: Private key (if not cached)

        Returns:
            Decrypted data
        """
        try:
            # Get private key
            if private_key_pem:
                private_key = serialization.load_pem_private_key(
                    private_key_pem, password=None
                )
            elif device_id in self.rsa_keys:
                private_key, _ = self.rsa_keys[device_id]
            else:
                raise ValueError(f"No RSA key for device: {device_id}")

            # Decrypt
            plaintext = private_key.decrypt(
                ciphertext,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )

            return plaintext

        except Exception as e:
            self.logger.error(
                "Failed to decrypt with private key", device_id=device_id, error=str(e)
            )
            raise

    def rotate_device_key(self, device_id: str) -> bytes:
        """
        Rotate encryption key for device

        Args:
            device_id: Device identifier

        Returns:
            New encryption key
        """
        try:
            # Generate new key
            new_key = self.generate_device_key(device_id)

            self.logger.info("Rotated device encryption key", device_id=device_id)

            return new_key

        except Exception as e:
            self.logger.error(
                "Failed to rotate device key", device_id=device_id, error=str(e)
            )
            raise

    def check_key_rotation(self) -> List[str]:
        """
        Check which devices need key rotation

        Returns:
            List of device IDs needing rotation
        """
        devices_needing_rotation = []
        now = datetime.utcnow()

        for device_id, metadata in self.key_metadata.items():
            if metadata["rotation_due"] <= now:
                devices_needing_rotation.append(device_id)

        if devices_needing_rotation:
            self.logger.warning(
                "Devices need key rotation",
                count=len(devices_needing_rotation),
                devices=devices_needing_rotation,
            )

        return devices_needing_rotation

    def get_status(self) -> Dict[str, Any]:
        """Get encryption manager status"""
        devices_needing_rotation = self.check_key_rotation()

        return {
            "default_method": self.default_method,
            "device_keys_cached": len(self.device_keys),
            "rsa_keys_cached": len(self.rsa_keys),
            "key_rotation_days": self.key_rotation_days,
            "devices_needing_rotation": len(devices_needing_rotation),
        }
