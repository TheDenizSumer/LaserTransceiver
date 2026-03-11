import asyncio
import time

from outQueue import outLaserWorker, TYPE_ACK, TYPE_DATA, TYPE_SB, TYPE_NEXT

async def main():
    print("starting main worker")

    queue = asyncio.PriorityQueue()
    workerTask = asyncio.create_task(outLaserWorker(queue))
    
    await asyncio.sleep(0.5) # proof of life

    await queue.put((TYPE_DATA, b"Test message with a message larger that 3 bytes")) # send data
    
    #await queue.put((TYPE_ACK, b"ACK data")) # send ack


    await asyncio.sleep(3.0) # let the first chunk loop a bit
    await queue.put((TYPE_NEXT, b"")) # let outQueue know that an ack has been recived and to move to the next chunk

    await asyncio.sleep(3.0) # let the second chunk loop a bit
    
    # wait for the worker to clear the buffer
    await asyncio.sleep(2.0)
    
    # clean up and exit
    workerTask.cancel()
    print("\nstopped main")

if __name__ == "__main__":
    asyncio.run(main())