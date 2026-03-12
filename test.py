from outQueue import transmitPacket
import asyncio

packet_data = 0b0100100110110 # Example packet data
async def main():
    await transmitPacket(packet_data)
asyncio.run(main())