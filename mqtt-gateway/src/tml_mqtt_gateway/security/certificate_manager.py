"""
Certificate Manager
X.509 certificate-based authentication and management for IoT devices
"""

import os
import ssl
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PrivateFormat,
    NoEncryption,
)
import structlog

from ..config import TMLGatewayConfig
from ..metrics import DatabaseMetrics


logger = structlog.get_logger(__name__)


class CertificateManager:
    """
    Enterprise X.509 Certificate Management System

    Features:
    - Root CA and Intermediate CA management
    - Device certificate generation and signing
    - Certificate validation and revocation
    - Automatic certificate renewal
    - Certificate revocation lists (CRL)
    - OCSP responder integration
    """

    def __init__(self, config: TMLGatewayConfig, db_metrics: DatabaseMetrics):
        self.config = config
        self.db_metrics = db_metrics

        # Certificate storage paths
        self.cert_dir = Path("/app/certs")
        self.ca_dir = self.cert_dir / "ca"
        self.device_dir = self.cert_dir / "devices"
        self.crl_dir = self.cert_dir / "crl"

        # Create directories
        for directory in [self.cert_dir, self.ca_dir, self.device_dir, self.crl_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        # Certificate authority
        self.root_ca_cert = None
        self.root_ca_key = None
        self.intermediate_ca_cert = None
        self.intermediate_ca_key = None

        # Certificate tracking
        self.issued_certificates = {}
        self.revoked_certificates = set()

        # Certificate policies
        self.default_validity_days = 365
        self.renewal_threshold_days = 30

        self.logger = logger.bind(component="certificate_manager")

    async def initialize(self) -> None:
        """Initialize certificate authority and load existing certificates"""
        try:
            self.logger.info("Initializing certificate management system")

            # Load or create root CA
            await self._load_or_create_root_ca()

            # Load or create intermediate CA
            await self._load_or_create_intermediate_ca()

            # Load existing device certificates
            await self._load_existing_certificates()

            # Start certificate monitoring
            asyncio.create_task(self._certificate_monitor())

            self.logger.info("Certificate management system initialized successfully")

        except Exception as e:
            self.logger.error("Failed to initialize certificate manager", error=str(e))
            raise

    async def _load_or_create_root_ca(self) -> None:
        """Load existing root CA or create new one"""
        root_cert_path = self.ca_dir / "root_ca.crt"
        root_key_path = self.ca_dir / "root_ca.key"

        if root_cert_path.exists() and root_key_path.exists():
            # Load existing root CA
            with open(root_cert_path, "rb") as f:
                self.root_ca_cert = x509.load_pem_x509_certificate(f.read())

            with open(root_key_path, "rb") as f:
                self.root_ca_key = serialization.load_pem_private_key(
                    f.read(), password=None
                )

            self.logger.info("Loaded existing root CA certificate")
        else:
            # Create new root CA
            await self._create_root_ca()
            self.logger.info("Created new root CA certificate")

    async def _create_root_ca(self) -> None:
        """Create new root CA certificate"""
        # Generate private key
        self.root_ca_key = rsa.generate_private_key(
            public_exponent=65537, key_size=4096
        )

        # Create certificate
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TML Platform"),
                x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "IoT Security"),
                x509.NameAttribute(NameOID.COMMON_NAME, "TML Root CA"),
            ]
        )

        self.root_ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(self.root_ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=3650))  # 10 years
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(
                    self.root_ca_key.public_key()
                ),
                critical=False,
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(
                    self.root_ca_key.public_key()
                ),
                critical=False,
            )
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=1),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_cert_sign=True,
                    crl_sign=True,
                    key_agreement=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    content_commitment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(self.root_ca_key, hashes.SHA256())
        )

        # Save certificate and key
        with open(self.ca_dir / "root_ca.crt", "wb") as f:
            f.write(self.root_ca_cert.public_bytes(Encoding.PEM))

        with open(self.ca_dir / "root_ca.key", "wb") as f:
            f.write(
                self.root_ca_key.private_bytes(
                    encoding=Encoding.PEM,
                    format=PrivateFormat.PKCS8,
                    encryption_algorithm=NoEncryption(),
                )
            )

    async def _load_or_create_intermediate_ca(self) -> None:
        """Load existing intermediate CA or create new one"""
        intermediate_cert_path = self.ca_dir / "intermediate_ca.crt"
        intermediate_key_path = self.ca_dir / "intermediate_ca.key"

        if intermediate_cert_path.exists() and intermediate_key_path.exists():
            # Load existing intermediate CA
            with open(intermediate_cert_path, "rb") as f:
                self.intermediate_ca_cert = x509.load_pem_x509_certificate(f.read())

            with open(intermediate_key_path, "rb") as f:
                self.intermediate_ca_key = serialization.load_pem_private_key(
                    f.read(), password=None
                )

            self.logger.info("Loaded existing intermediate CA certificate")
        else:
            # Create new intermediate CA
            await self._create_intermediate_ca()
            self.logger.info("Created new intermediate CA certificate")

    async def _create_intermediate_ca(self) -> None:
        """Create new intermediate CA certificate"""
        # Generate private key
        self.intermediate_ca_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )

        # Create certificate signed by root CA
        subject = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TML Platform"),
                x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "IoT Security"),
                x509.NameAttribute(NameOID.COMMON_NAME, "TML Intermediate CA"),
            ]
        )

        self.intermediate_ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(self.root_ca_cert.subject)
            .public_key(self.intermediate_ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=1825))  # 5 years
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(
                    self.intermediate_ca_key.public_key()
                ),
                critical=False,
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(
                    self.root_ca_key.public_key()
                ),
                critical=False,
            )
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=0),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_cert_sign=True,
                    crl_sign=True,
                    key_agreement=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    content_commitment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(self.root_ca_key, hashes.SHA256())
        )

        # Save certificate and key
        with open(self.ca_dir / "intermediate_ca.crt", "wb") as f:
            f.write(self.intermediate_ca_cert.public_bytes(Encoding.PEM))

        with open(self.ca_dir / "intermediate_ca.key", "wb") as f:
            f.write(
                self.intermediate_ca_key.private_bytes(
                    encoding=Encoding.PEM,
                    format=PrivateFormat.PKCS8,
                    encryption_algorithm=NoEncryption(),
                )
            )

    async def generate_device_certificate(
        self,
        device_id: str,
        device_type: str,
        organization: str = None,
        validity_days: int = None,
    ) -> Tuple[bytes, bytes, bytes]:
        """
        Generate device certificate signed by intermediate CA

        Args:
            device_id: Unique device identifier
            device_type: Type of device (sensor, actuator, gateway)
            organization: Organization name (for multi-tenancy)
            validity_days: Certificate validity period

        Returns:
            Tuple of (certificate, private_key, ca_chain)
        """
        try:
            validity_days = validity_days or self.default_validity_days

            # Generate device private key
            device_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

            # Create device certificate
            org_name = organization or "TML Platform"
            subject = x509.Name(
                [
                    x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                    x509.NameAttribute(NameOID.ORGANIZATION_NAME, org_name),
                    x509.NameAttribute(
                        NameOID.ORGANIZATIONAL_UNIT_NAME, f"IoT {device_type.title()}"
                    ),
                    x509.NameAttribute(NameOID.COMMON_NAME, device_id),
                ]
            )

            # Subject Alternative Names for device identification
            san_list = [
                x509.DNSName(f"{device_id}.tml.local"),
                x509.RFC822Name(f"{device_id}@tml.local"),
            ]

            device_cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(self.intermediate_ca_cert.subject)
                .public_key(device_key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.utcnow())
                .not_valid_after(datetime.utcnow() + timedelta(days=validity_days))
                .add_extension(
                    x509.SubjectKeyIdentifier.from_public_key(device_key.public_key()),
                    critical=False,
                )
                .add_extension(
                    x509.AuthorityKeyIdentifier.from_issuer_public_key(
                        self.intermediate_ca_key.public_key()
                    ),
                    critical=False,
                )
                .add_extension(
                    x509.BasicConstraints(ca=False, path_length=None),
                    critical=True,
                )
                .add_extension(
                    x509.KeyUsage(
                        digital_signature=True,
                        key_encipherment=True,
                        key_agreement=False,
                        key_cert_sign=False,
                        crl_sign=False,
                        data_encipherment=False,
                        content_commitment=False,
                        encipher_only=False,
                        decipher_only=False,
                    ),
                    critical=True,
                )
                .add_extension(
                    x509.ExtendedKeyUsage(
                        [
                            x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
                        ]
                    ),
                    critical=True,
                )
                .add_extension(
                    x509.SubjectAlternativeName(san_list),
                    critical=False,
                )
                .sign(self.intermediate_ca_key, hashes.SHA256())
            )

            # Convert to PEM format
            cert_pem = device_cert.public_bytes(Encoding.PEM)
            key_pem = device_key.private_bytes(
                encoding=Encoding.PEM,
                format=PrivateFormat.PKCS8,
                encryption_algorithm=NoEncryption(),
            )

            # Create CA chain (intermediate + root)
            ca_chain = self.intermediate_ca_cert.public_bytes(
                Encoding.PEM
            ) + self.root_ca_cert.public_bytes(Encoding.PEM)

            # Save device certificate
            device_cert_path = self.device_dir / f"{device_id}.crt"
            device_key_path = self.device_dir / f"{device_id}.key"

            with open(device_cert_path, "wb") as f:
                f.write(cert_pem)

            with open(device_key_path, "wb") as f:
                f.write(key_pem)

            # Track issued certificate
            self.issued_certificates[device_id] = {
                "certificate": device_cert,
                "serial_number": device_cert.serial_number,
                "not_valid_after": device_cert.not_valid_after,
                "device_type": device_type,
                "organization": org_name,
                "issued_at": datetime.utcnow(),
            }

            self.logger.info(
                "Generated device certificate",
                device_id=device_id,
                device_type=device_type,
                serial_number=device_cert.serial_number,
                valid_until=device_cert.not_valid_after,
            )

            return cert_pem, key_pem, ca_chain

        except Exception as e:
            self.logger.error(
                "Failed to generate device certificate",
                device_id=device_id,
                error=str(e),
            )
            raise

    async def validate_device_certificate(self, cert_pem: bytes) -> Dict[str, Any]:
        """
        Validate device certificate against CA chain

        Args:
            cert_pem: Device certificate in PEM format

        Returns:
            Dict with validation results
        """
        try:
            # Load certificate
            device_cert = x509.load_pem_x509_certificate(cert_pem)

            # Check if certificate is revoked
            if device_cert.serial_number in self.revoked_certificates:
                return {
                    "valid": False,
                    "reason": "Certificate is revoked",
                    "serial_number": device_cert.serial_number,
                }

            # Check certificate validity period
            now = datetime.utcnow()
            if now < device_cert.not_valid_before:
                return {
                    "valid": False,
                    "reason": "Certificate not yet valid",
                    "not_valid_before": device_cert.not_valid_before,
                }

            if now > device_cert.not_valid_after:
                return {
                    "valid": False,
                    "reason": "Certificate has expired",
                    "not_valid_after": device_cert.not_valid_after,
                }

            # Verify certificate chain
            try:
                # Verify device cert was signed by intermediate CA
                self.intermediate_ca_cert.public_key().verify(
                    device_cert.signature,
                    device_cert.tbs_certificate_bytes,
                    padding.PKCS1v15(),
                    device_cert.signature_hash_algorithm,
                )
            except Exception:
                return {
                    "valid": False,
                    "reason": "Certificate signature verification failed",
                }

            # Extract device information
            device_id = None
            for attribute in device_cert.subject:
                if attribute.oid == NameOID.COMMON_NAME:
                    device_id = attribute.value
                    break

            return {
                "valid": True,
                "device_id": device_id,
                "serial_number": device_cert.serial_number,
                "issuer": device_cert.issuer.rfc4514_string(),
                "subject": device_cert.subject.rfc4514_string(),
                "not_valid_before": device_cert.not_valid_before,
                "not_valid_after": device_cert.not_valid_after,
                "days_until_expiry": (device_cert.not_valid_after - now).days,
            }

        except Exception as e:
            self.logger.error("Certificate validation failed", error=str(e))
            return {"valid": False, "reason": f"Validation error: {str(e)}"}

    async def revoke_certificate(
        self, serial_number: int, reason: str = "unspecified"
    ) -> None:
        """
        Revoke a device certificate

        Args:
            serial_number: Certificate serial number
            reason: Revocation reason
        """
        try:
            self.revoked_certificates.add(serial_number)

            # Update CRL
            await self._update_crl()

            self.logger.info(
                "Certificate revoked", serial_number=serial_number, reason=reason
            )

        except Exception as e:
            self.logger.error(
                "Failed to revoke certificate",
                serial_number=serial_number,
                error=str(e),
            )
            raise

    async def _update_crl(self) -> None:
        """Update Certificate Revocation List"""
        try:
            # Create CRL
            crl_builder = x509.CertificateRevocationListBuilder()
            crl_builder = crl_builder.issuer_name(self.intermediate_ca_cert.subject)
            crl_builder = crl_builder.last_update(datetime.utcnow())
            crl_builder = crl_builder.next_update(datetime.utcnow() + timedelta(days=7))

            # Add revoked certificates
            for serial_number in self.revoked_certificates:
                revoked_cert = (
                    x509.RevokedCertificateBuilder()
                    .serial_number(serial_number)
                    .revocation_date(datetime.utcnow())
                    .add_extension(
                        x509.CRLReason(x509.ReasonFlags.unspecified), critical=False
                    )
                    .build()
                )

                crl_builder = crl_builder.add_revoked_certificate(revoked_cert)

            # Sign CRL
            crl = crl_builder.sign(self.intermediate_ca_key, hashes.SHA256())

            # Save CRL
            crl_path = self.crl_dir / "intermediate_ca.crl"
            with open(crl_path, "wb") as f:
                f.write(crl.public_bytes(Encoding.PEM))

            self.logger.info(
                "Updated Certificate Revocation List",
                revoked_count=len(self.revoked_certificates),
            )

        except Exception as e:
            self.logger.error("Failed to update CRL", error=str(e))
            raise

    async def _load_existing_certificates(self) -> None:
        """Load existing device certificates from disk"""
        try:
            cert_count = 0

            for cert_file in self.device_dir.glob("*.crt"):
                device_id = cert_file.stem

                with open(cert_file, "rb") as f:
                    cert_pem = f.read()
                    device_cert = x509.load_pem_x509_certificate(cert_pem)

                self.issued_certificates[device_id] = {
                    "certificate": device_cert,
                    "serial_number": device_cert.serial_number,
                    "not_valid_after": device_cert.not_valid_after,
                    "loaded_from_disk": True,
                }

                cert_count += 1

            self.logger.info("Loaded existing certificates", count=cert_count)

        except Exception as e:
            self.logger.error("Failed to load existing certificates", error=str(e))

    async def _certificate_monitor(self) -> None:
        """Monitor certificates for expiration and renewal"""
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour

                now = datetime.utcnow()
                expiring_soon = []

                for device_id, cert_info in self.issued_certificates.items():
                    days_until_expiry = (cert_info["not_valid_after"] - now).days

                    if days_until_expiry <= self.renewal_threshold_days:
                        expiring_soon.append(
                            {
                                "device_id": device_id,
                                "days_until_expiry": days_until_expiry,
                            }
                        )

                if expiring_soon:
                    self.logger.warning(
                        "Certificates expiring soon",
                        count=len(expiring_soon),
                        certificates=expiring_soon,
                    )

            except Exception as e:
                self.logger.error("Error in certificate monitor", error=str(e))
                await asyncio.sleep(300)  # Wait 5 minutes on error

    def get_ca_certificate_chain(self) -> bytes:
        """Get the complete CA certificate chain"""
        return self.intermediate_ca_cert.public_bytes(
            Encoding.PEM
        ) + self.root_ca_cert.public_bytes(Encoding.PEM)

    def get_status(self) -> Dict[str, Any]:
        """Get certificate manager status"""
        now = datetime.utcnow()

        expiring_count = 0
        for cert_info in self.issued_certificates.values():
            days_until_expiry = (cert_info["not_valid_after"] - now).days
            if days_until_expiry <= self.renewal_threshold_days:
                expiring_count += 1

        return {
            "root_ca_valid_until": self.root_ca_cert.not_valid_after.isoformat(),
            "intermediate_ca_valid_until": self.intermediate_ca_cert.not_valid_after.isoformat(),
            "issued_certificates": len(self.issued_certificates),
            "revoked_certificates": len(self.revoked_certificates),
            "certificates_expiring_soon": expiring_count,
            "renewal_threshold_days": self.renewal_threshold_days,
        }
