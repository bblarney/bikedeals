"""create the Instagram poster's tables

Revision ID: b8e2d5c47f13
Revises: a7d3e91c5f28
Create Date: 2026-08-28 00:00:00.000000

Three small tables backing one automated Instagram post per day.

``social_state`` holds the long-lived access token. That is a deliberate choice
over a GitHub Actions secret: the token has to be rewritten roughly every 50
days when it is refreshed, and letting a workflow write repo secrets means
keeping a PAT with that scope in the repo, which is a strictly worse credential
to hold than the token it would protect.

``social_images`` holds rendered JPEGs, and is the one table here that would
grow without help. Instagram will not accept image bytes over the API: it takes
a public URL, cURLs it once at publish time, and serves its own copy from then
on. So these rows are a delivery mechanism with a 30-day prune, not an archive,
and deleting one cannot affect a post that is already live.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b8e2d5c47f13'
down_revision: Union[str, Sequence[str], None] = 'a7d3e91c5f28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'social_state',
        sa.Column('key', sa.Text(), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )

    op.create_table(
        'social_posts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_key', sa.Text(), nullable=True),
        sa.Column('bike_id', sa.Text(), nullable=False),
        sa.Column('ig_media_id', sa.Text(), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    # Both lookups the selector makes: "has this product been posted lately"
    # for the 87% of listings carrying a SKU, and the bike_id fallback for the
    # rest.
    op.create_index(
        'idx_social_posts_product_key_posted', 'social_posts', ['product_key', 'posted_at']
    )
    op.create_index('idx_social_posts_bike_posted', 'social_posts', ['bike_id', 'posted_at'])

    op.create_table(
        'social_images',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('jpeg', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    # Supports the nightly prune, which is the only query that does not go
    # straight to the primary key.
    op.create_index('idx_social_images_created_at', 'social_images', ['created_at'])


def downgrade() -> None:
    op.drop_index('idx_social_images_created_at', table_name='social_images')
    op.drop_table('social_images')
    op.drop_index('idx_social_posts_bike_posted', table_name='social_posts')
    op.drop_index('idx_social_posts_product_key_posted', table_name='social_posts')
    op.drop_table('social_posts')
    op.drop_table('social_state')
