import asyncio
import os
from typing import Iterable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ...paul_bot.application.poll import Poll

from mixpanel import Mixpanel
from mixpanel_async import AsyncBufferedConsumer

# Creating an AsyncBufferedConsumer instance
mp_consumer = AsyncBufferedConsumer(max_size=25)
# Creating a Mixpanel instance and registering the AsyncBufferedConsumer as the consumer
mp_client = Mixpanel(os.environ['DISCORD_MIXPANEL_TOKEN'], consumer=mp_consumer)


class Option:
    """Represents an option that a user can choose in a poll."""

    def __init__(
            self,
            option_id: Optional[int],
            label: str,
            votes: Iterable[int],
            poll: "Poll",
            index: int,
            author_id: Optional[int],
    ):
        self.__option_id = option_id
        self.__label = label
        self.__votes = set(votes)
        self.__poll = poll
        self.__index = index
        self.__author_id = author_id

    @property
    def option_id(self) -> int:
        """The id of the option."""
        if self.__option_id is None:
            raise ValueError(
                "Option doesn't have an ID yet since it has not been added to the"
                " database."
            )
        return self.__option_id

    @property
    def label(self) -> str:
        """The label of the option."""
        return self.__label

    @property
    def votes(self) -> set[int]:
        """The set of IDs of members who voted on this option."""
        return self.__votes.copy()

    @property
    def poll(self) -> "Poll":
        """The Poll that the option belongs to."""
        return self.__poll

    @property
    def index(self) -> int:
        """The index of the option in the poll."""
        return self.__index

    @property
    def author_id(self) -> Optional[int]:
        """The ID of the member who added the option, or None if the option existed from poll creation."""
        return self.__author_id

    @property
    def vote_count(self) -> int:
        """Get the number of votes for this option."""
        return len(self.__votes)

    def remove_vote(self, voter_id: int):
        """Remove a vote from the given user on this option. If no such vote exists, nothing happens.

        This method does not remove the vote from the database. To remove the vote from the database, use the `delete_vote` method.

        Args:
            voter_id: The ID of the user whose vote is to be removed.
        """
        self.__votes.discard(voter_id)

    def delete_vote(self, voter_id: int):
        """Delete a vote from the given user on this option. If no such vote exists, nothing happens.

        This method deletes the vote from the database. To remove the vote from the option without affecting the database (for example if the vote has already been removed from the database), use the `remove_vote` method instead.

        Args:
            voter_id: The ID of the user whose vote is to be deleted.
        """

        self.remove_vote(voter_id)

    def add_vote(self, voter_id: int):
        """Add a vote from the given user on this option. If such a vote already exists, nothing happens. If the poll cannot have more than one vote per user, all other votes from this user are removed.

        Args:
            voter_id: The ID of the user whose vote is to be added.
        """
        if not self.poll.allow_multiple_votes:
            self.poll.remove_votes_from(voter_id)
        self.__votes.add(voter_id)

    def toggle_vote(self, voter_id: int):
        """Toggle a user's vote on this option. If adding their vote would cause too many votes from the same user, the rest of their votes are removed.

        Args:
            voter_id: The ID of the user to toggle the vote of.
        """
        if voter_id in self.__votes:
            self.delete_vote(voter_id)
        else:
            self.add_vote(voter_id)

    @classmethod
    async def create_option(
            cls, label: str, poll: "Poll", author_id: Optional[int] = None
    ) -> "Option":
        """Create a new option for the given poll and add it to the database.

        Args:
            label: The label of the option to create.
            poll: The poll to create the option for.
            author_id: The ID of the member who created the option, or None, if the option is being created at poll creation.

        Returns:
            The created option.
        """
        return (await Option.create_options((label,), poll, author_id))[0]

    @classmethod
    async def create_options(
            cls,
            labels: Iterable[str],
            poll: "Poll",
            author_id: Optional[int] = None,
    ) -> list["Option"]:
        """Create new Option objects for the given poll and add them to the database.

        Args:
            labels: The labels of the options to add.
            poll: The ID of the poll that this option belongs to.
            author_id: The ID of the person who added this option, or None if the options were created at the time of creation.

        Returns:
            The new Option objects.
        """
        options = [
            Option(None, label, (), poll, index, author_id)
            for index, label in enumerate(
                labels,
                start=max((option.index for option in poll.options), default=-1) + 1,
            )
        ]

        return options
