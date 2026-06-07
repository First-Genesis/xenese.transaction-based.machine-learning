using Microsoft.EntityFrameworkCore.Migrations;
using Npgsql.EntityFrameworkCore.PostgreSQL.Metadata;

#nullable disable

namespace TML.Storage.Migrations
{
    /// <inheritdoc />
    public partial class InitialCreate : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "Transactions",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    Data = table.Column<string>(type: "jsonb", nullable: false),
                    Source = table.Column<string>(type: "character varying(100)", maxLength: 100, nullable: false),
                    Metadata = table.Column<string>(type: "jsonb", nullable: false),
                    Status = table.Column<int>(type: "integer", nullable: false),
                    CreatedAt = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    ProcessedAt = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true),
                    ProcessingTimeMs = table.Column<double>(type: "double precision", nullable: true),
                    ModelId = table.Column<Guid>(type: "uuid", nullable: true),
                    ErrorDetails = table.Column<string>(type: "text", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Transactions", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "Models",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    TransactionId = table.Column<Guid>(type: "uuid", nullable: false),
                    ParentModelId = table.Column<Guid>(type: "uuid", nullable: true),
                    InheritanceDepth = table.Column<int>(type: "integer", nullable: false),
                    Status = table.Column<int>(type: "integer", nullable: false),
                    CreatedAt = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    UpdatedAt = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    Version = table.Column<int>(type: "integer", nullable: false),
                    Parameters = table.Column<string>(type: "jsonb", nullable: false),
                    Location = table.Column<string>(type: "jsonb", nullable: false),
                    Metrics = table.Column<string>(type: "jsonb", nullable: false),
                    PhysicsValidation = table.Column<string>(type: "jsonb", nullable: false),
                    ArtifactLocation = table.Column<string>(type: "character varying(500)", maxLength: 500, nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Models", x => x.Id);
                    table.ForeignKey(
                        name: "FK_Models_Models_ParentModelId",
                        column: x => x.ParentModelId,
                        principalTable: "Models",
                        principalColumn: "Id");
                    table.ForeignKey(
                        name: "FK_Models_Transactions_TransactionId",
                        column: x => x.TransactionId,
                        principalTable: "Transactions",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            // Create indexes for performance
            migrationBuilder.CreateIndex(
                name: "IX_Transactions_CreatedAt",
                table: "Transactions",
                column: "CreatedAt");

            migrationBuilder.CreateIndex(
                name: "IX_Transactions_Status",
                table: "Transactions",
                column: "Status");

            migrationBuilder.CreateIndex(
                name: "IX_Transactions_Source",
                table: "Transactions",
                column: "Source");

            migrationBuilder.CreateIndex(
                name: "IX_Models_TransactionId",
                table: "Models",
                column: "TransactionId");

            migrationBuilder.CreateIndex(
                name: "IX_Models_ParentModelId",
                table: "Models",
                column: "ParentModelId");

            migrationBuilder.CreateIndex(
                name: "IX_Models_Status",
                table: "Models",
                column: "Status");

            migrationBuilder.CreateIndex(
                name: "IX_Models_CreatedAt",
                table: "Models",
                column: "CreatedAt");

            migrationBuilder.CreateIndex(
                name: "IX_Models_InheritanceDepth",
                table: "Models",
                column: "InheritanceDepth");

            // Create GIN indexes for JSONB columns for fast queries
            migrationBuilder.Sql("CREATE INDEX IX_Transactions_Data_GIN ON \"Transactions\" USING GIN (\"Data\");");
            migrationBuilder.Sql("CREATE INDEX IX_Transactions_Metadata_GIN ON \"Transactions\" USING GIN (\"Metadata\");");
            migrationBuilder.Sql("CREATE INDEX IX_Models_Parameters_GIN ON \"Models\" USING GIN (\"Parameters\");");
            migrationBuilder.Sql("CREATE INDEX IX_Models_Location_GIN ON \"Models\" USING GIN (\"Location\");");
            migrationBuilder.Sql("CREATE INDEX IX_Models_Metrics_GIN ON \"Models\" USING GIN (\"Metrics\");");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "Models");

            migrationBuilder.DropTable(
                name: "Transactions");
        }
    }
}
